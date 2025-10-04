from core.models.game_state import GameState
from core.tools.session import SessionTool
from core.models.protocol import EventBatch, PlannerResponse, SimplePlannerResponse
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

# 确保环境变量已加载
load_dotenv()

# 延迟初始化全局变量（避免导入时的环境变量问题）
openai_client = None

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
    for image in images:
        try:
            image_content = image.to_openai_format()
            user_content.append(image_content)
        except Exception as e:
            print(f"Warning: Failed to process image: {str(e)}")
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

def _convert_simple_to_full_response(simple_response: SimplePlannerResponse, session_id: str) -> PlannerResponse:
    """将SimplePlannerResponse转换为完整的PlannerResponse，将简单数字ID转换为完整格式"""
    
    # 1. 生成Goal ID（SimplePlannerResponse没有goal_id字段，总是生成新的）
    goal_id = new_goal_id(session_id, 1)
    
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
        planner_system_prompt = await generate_planner_system_prompt(event_batch)

        # 4. 调用OpenAI获取计划，直接返回PlannerResponse
        planner_response = await _call_openai_for_plan(event_batch.events, planner_system_prompt, event_batch.session_id)
        
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
        
        # 返回错误响应
        fallback_goal_id = new_goal_id(event_batch.session_id, 1)
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

async def _call_openai_for_plan(events, system_prompt: str, session_id: str) -> PlannerResponse:
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
    
    try:
        # 选择合适的模型 - 如果有图片使用vision模型
        model = "gpt-4o" if images else "gpt-4o"
        
        # 调用OpenAI API
        response = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,       # 降低随意性，利于结构稳定
            max_tokens=1800,
            response_format=get_planner_response_schema(strict=False),  # 使用兼容模式避免strict mode问题
            seed=7                 # 可复现（可按需移除）
        )

        content = response.choices[0].message.content  # 严格模式下应为合法 JSON 字符串
        data = json.loads(content)

        # 解析为SimplePlannerResponse
        simple_response = SimplePlannerResponse.model_validate(data)
        
        # 转换为完整的PlannerResponse，自动生成所有ID
        return _convert_simple_to_full_response(simple_response, session_id)

    except Exception as e:
        import traceback
        error_details = f"OpenAI call failed: {str(e)}\nTraceback: {traceback.format_exc()}"
        print(error_details)
        
        # 兜底：若出现意外（比如网络/解析异常），返回一个安全的空计划
        fallback_goal_id = new_goal_id(session_id, 1)
        return PlannerResponse(
            session_id=session_id,
            goal_id=fallback_goal_id,
            goal_label="Planner fallback due to error",
            talk_to_player="I'm having a brief issue planning; I'll try a simpler approach this turn.",
            plan=[]
        )

# 同步包装器，供外部调用
def plan(event_batch) -> dict:
    """同步包装器，调用异步的plan_async函数
    
    返回包含PlannerResponse和debug_info的字典
    """
    return asyncio.run(plan_async(event_batch))
