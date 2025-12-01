from core.models.game_state import GameState
from core.tools.session import SessionTool
from core.models.protocol import EventBatch, PlannerResponse, SimplePlannerResponse
from pydantic import ValidationError
from core.models.base import Plan, Image, Event
from core.prompts.system_prompt import generate_planner_system_prompt
from core.schemas.openai_schemas import get_planner_response_schema
from core.tools.id_generator import new_goal_id, new_plan_id
import json
import asyncio
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import logging

# 确保环境变量已加载
load_dotenv()

# 初始化logger
logger = logging.getLogger(__name__)

# 延迟初始化全局变量（避免导入时的环境变量问题）
openai_client = None
# 在planner内部跟踪每个session的goal序号，避免API侧改动
_session_goal_sequences: Dict[str, int] = {}

def _next_goal_sequence(session_id: str) -> int:
    seq = _session_goal_sequences.get(session_id, 0) + 1
    _session_goal_sequences[session_id] = seq
    return seq

def _ensure_initialized():
    """确保全局变量已初始化"""
    global openai_client
    if openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Please set it in environment or .env file")
        
        openai_client = AsyncOpenAI(api_key=api_key)

def _extract_images_from_events(events: List[Event]) -> List[Image]:
    """从事件列表中提取所有图片
    
    Args:
        events: 事件列表
        
    Returns:
        List[Image]: 提取到的图片列表
    """
    images = []
    
    for event in events:
        try:
            # 检查不同类型的事件payload中的图片
            if hasattr(event, 'payload'):
                payload = event.payload
                
                # PlayerSpeakPayload中的单张图片
                if hasattr(payload, 'image') and payload.image:
                    if isinstance(payload.image, Image):
                        images.append(payload.image)
                
                # AgentContinuePlanPayload和AgentPerceptionPayload中的图片列表
                elif hasattr(payload, 'image') and payload.image and isinstance(payload.image, list):
                    for img in payload.image:
                        if isinstance(img, Image):
                            images.append(img)
                            
        except Exception as e:
            print(f"Warning: Failed to extract image from event {event.type}: {str(e)}")
            continue
    
    return images

def _build_openai_messages(user_text: str, images: List[Image], system_prompt: str) -> List[Dict[str, Any]]:
    """构建OpenAI API消息格式，支持多模态输入
    
    Args:
        user_text: 用户文本输入
        images: 图片列表
        system_prompt: 系统提示词
        
    Returns:
        List[Dict]: OpenAI API格式的消息列表
    """
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # 构建用户消息内容
    user_content = []
    
    # 添加文本内容
    if user_text:
        user_content.append({
            "type": "text",
            "text": user_text
        })
    
    # 添加图片内容
    for idx, image in enumerate(images):
        try:
            image_content = image.to_openai_format()
            # Log image format for debugging
            if image.base64:
                base64_preview = image.base64[:50] if len(image.base64) > 50 else image.base64
                logger.info(f"[Image Format] Image {idx + 1}: base64 length={len(image.base64)}, preview={base64_preview}...")
                # Check if base64 has proper format
                if not image.base64.startswith('data:image/'):
                    logger.warning(f"[Image Format] Image {idx + 1}: base64 missing data URI prefix, will be auto-added")
            user_content.append(image_content)
        except Exception as e:
            logger.error(f"[Image Format] Failed to process image {idx + 1}: {str(e)}", exc_info=True)
            continue
    
    # 如果没有任何内容，添加默认文本
    if not user_content:
        user_content.append({
            "type": "text", 
            "text": "No specific user input"
        })
    
    messages.append({
        "role": "user",
        "content": user_content
    })
    
    return messages

def _convert_simple_to_full_response(simple_response: SimplePlannerResponse, session_id: str, goal_sequence: int) -> PlannerResponse:
    """将SimplePlannerResponse转换为完整的PlannerResponse，将简单数字ID转换为完整格式
    
    Args:
        simple_response: 简单响应对象
        session_id: 会话ID
        goal_sequence: Goal序列号（从1开始）
    """
    
    # 1. 生成Goal ID（使用传入的序列号）
    goal_id = new_goal_id(session_id, goal_sequence)
    
    # 2. 创建简单ID到完整ID的映射
    simple_to_full_mapping = {}  # 简单ID -> 完整ID 的映射
    
    # 3. 第一轮：转换所有plan的ID
    full_plans = []
    for i, plan in enumerate(simple_response.plan):
        # 生成完整的plan ID
        full_plan_id = new_plan_id(goal_id, i + 1)
        simple_to_full_mapping[plan.id] = full_plan_id
        
        # 创建新的plan对象，暂时保持原有的depends_on
        full_plan = Plan(
            id=full_plan_id,
            action_type=plan.action_type,
            description=plan.description,
            depends_on=plan.depends_on  # 暂时保持原样，下一步转换
        )
        full_plans.append(full_plan)
    
    # 4. 第二轮：转换所有depends_on引用
    for full_plan in full_plans:
        if full_plan.depends_on:
            converted_depends = []
            for simple_dep_id in full_plan.depends_on:
                if simple_dep_id in simple_to_full_mapping:
                    converted_depends.append(simple_to_full_mapping[simple_dep_id])
            full_plan.depends_on = converted_depends if converted_depends else None
    
    # 5. 构建完整响应
    return PlannerResponse(
        session_id=session_id,
        goal_id=goal_id,
        goal_label=simple_response.goal_label,
        talk_to_player=simple_response.talk_to_player,
        plan=full_plans
    )

async def plan_async(event_batch: EventBatch) -> dict:
    """
    主要规划函数：EventBatch -> 立即对话 + 后续计划
    
    流程：
    1. 从EventBatch获取游戏状态（如果没有则创建默认状态）
    2. 生成Planner system prompt
    3. 调用LLM获取 {talk_to_player + plan}
    4. 返回PlannerResponse（立即对话 + 计划步骤）
    """
    # 确保所有全局变量已初始化
    _ensure_initialized()
    
    try:

        # 2. 生成系统提示词 - KISS原则：让 system_prompt 内部调用 context + manual
        logger.info("Generating planner context...")
        planner_system_prompt = await generate_planner_system_prompt(event_batch)

        # 4. 调用OpenAI获取计划，直接返回PlannerResponse
        seq = _next_goal_sequence(event_batch.session_id)
        planner_response = await _call_openai_for_plan(event_batch.events, planner_system_prompt, event_batch.session_id, seq)
        
        # 6. 返回PlannerResponse（立即对话 + 计划）
        return {
            "planner_response": planner_response,
            "debug_info": {
                "system_prompt": planner_system_prompt,
                "raw_plan": planner_response.model_dump()
            }
        }
        
    except Exception as e:
        import traceback
        error_details = f"Error in planner: {str(e)}\nTraceback: {traceback.format_exc()}"
        print(error_details)
        
        # 返回错误响应（使用内部序列号）
        seq = _next_goal_sequence(event_batch.session_id)
        fallback_goal_id = new_goal_id(event_batch.session_id, seq)
        return {
            "planner_response": PlannerResponse(
                session_id=event_batch.session_id,
                goal_id=fallback_goal_id,
                goal_label="Error occurred during planning",
                talk_to_player="Sorry, I encountered an error while planning. Could you try again?",
                plan=[]
            ),
            "debug_info": {
                "error": error_details,
                "system_prompt": None,
                "raw_plan": None
            }
        }

async def _call_openai_for_plan(events, system_prompt: str, session_id: str, goal_sequence: int) -> PlannerResponse:
    """调用 OpenAI，要求严格按 PlannerResponse 的 JSON Schema 返回，支持多模态输入。"""

    # 组装用户文本
    user_text = ""
    for event in events:
        if getattr(event, "type", None) == "player_speak":
            payload = getattr(event, "payload", None)
            if payload:
                # 支持新的强类型payload
                if hasattr(payload, 'text'):
                    txt = payload.text
                # 向后兼容字典格式
                elif isinstance(payload, dict):
                    txt = payload.get("text")
                else:
                    txt = None
                    
                if txt:
                    user_text += f"{txt} "
    
    user_text = user_text.strip() or "No specific user input"
    
    # 提取事件中的图片
    images = _extract_images_from_events(events)
    
    # 构建消息（支持多模态）
    messages = _build_openai_messages(user_text, images, system_prompt)
    
    MAX_RETRIES = 3
    
    for attempt in range(MAX_RETRIES):
        try:
            # 选择合适的模型 - 如果有图片使用vision模型
            model = "gpt-5-mini" if images else "gpt-5-mini"
            
            if attempt > 0:
                logger.info(f"Retrying planning (Attempt {attempt + 1}/{MAX_RETRIES})...")
            
            # 调用OpenAI API
            # Note: reasoning parameter is only available in /v1/responses endpoint, not in /v1/chat/completions
            # If you need reasoning, consider switching to Responses API when SDK supports it
            response = await openai_client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=8000,
                response_format=get_planner_response_schema(strict=False),  # 使用兼容模式避免strict mode问题
            )

            logger.info("Planner LLM response received.")

            choice = response.choices[0]
            
            # 检查 finish_reason
            if choice.finish_reason != "stop":
                logger.warning(f"OpenAI finish_reason: {choice.finish_reason}, may indicate incomplete response")
                if choice.finish_reason == "length":
                    # Log token usage details
                    if hasattr(response, 'usage'):
                        usage = response.usage
                        logger.error(f"Token limit reached. Usage: completion_tokens={usage.completion_tokens}, "
                                   f"reasoning_tokens={getattr(usage.completion_tokens_details, 'reasoning_tokens', 'N/A') if hasattr(usage, 'completion_tokens_details') else 'N/A'}")
            
            content = choice.message.content  # 严格模式下应为合法 JSON 字符串
            
            # 调试：检查内容是否为空
            if not content:
                logger.error(f"OpenAI returned empty content. Response: {response}")
                logger.error(f"Finish reason: {choice.finish_reason}")
                if choice.finish_reason == "length":
                    logger.error("All tokens were used for reasoning, none left for output. Consider increasing max_completion_tokens.")
                raise ValueError(f"OpenAI API returned empty content (finish_reason: {choice.finish_reason})")
            
            # 调试：记录实际返回的内容（前500字符）
            logger.debug(f"OpenAI response content (first 500 chars): {content[:500]}")
            
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON. Error: {e}")
                logger.error(f"Content (first 1000 chars): {content[:1000]}")
                raise ValueError(f"Invalid JSON response from OpenAI: {e}") from e

            # 解析为SimplePlannerResponse
            simple_response = SimplePlannerResponse.model_validate(data)
            
            # 转换为完整的PlannerResponse，自动生成所有ID
            return _convert_simple_to_full_response(simple_response, session_id, goal_sequence)

        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Validation Error or JSON Error: {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info("Retrying...")
                continue
            else:
                logger.error("Max retries reached for validation errors.")
                raise e

    # Should not reach here if raise e is called
    raise ValueError("Planning failed after max retries")

# 同步包装器，供外部调用
def plan(event_batch) -> dict:
    """同步包装器，调用异步的plan_async函数
    
    返回包含PlannerResponse和debug_info的字典
    """
    return asyncio.run(plan_async(event_batch))
