from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from core.models.protocol import EventBatch, CommandBatch, PlannerTestResponse, PlannerResponse
from core.models.texture import TextureJobRequest
from core.models.session import SessionClearRequest, SessionAck, MessageType
from core.models.protocol import PlanPermission
from core.tools.session import SessionTool
from core.tools.texture.texture_generator import TextureGenerator
from core.tools.planner import plan_async
from core.tools.executor import executor

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Voxel-AI Orchestrator")

# 启用CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入所需工具
import os

# 初始化工具
session_manager = SessionTool()
texture_generator = TextureGenerator()

@app.post("/events", response_model=PlannerResponse)
async def handle_events(batch: EventBatch):
    """
    统一事件处理入口
    
    接收来自Unity的事件批次，通过Planner进行规划输出PlannerResponse，返回给Unity等待确认。
    同时处理会话历史记录的更新。
    """
    try:
        # 记录完整的请求JSON
        import json
        logger.info("=" * 80)
        logger.info("Received full JSON:")
        logger.info(json.dumps(batch.dict(), indent=2, ensure_ascii=False))
        logger.info("=" * 80)
        
        # 确保会话存在（会自动处理空的session_id）
        session = session_manager.get_or_create_session(batch.session_id)
        batch.session_id = session.session_id  # 更新batch中的session_id（如果是新生成的）
        
        logger.info(f"Received event batch with {len(batch.events)} events for session {batch.session_id}")
        
        # 处理事件批次，更新会话历史
        session = session_manager.process_event_batch(batch)
        logger.info(f"Session history updated, current message count: {len(session.conversation_history)}")
        
        # 使用Planner架构处理事件（batch包含所有需要的信息）
        result = await plan_async(batch)
        planner_response = result["planner_response"]
        
        logger.info(f"Generated {len(planner_response.plan)} plan steps")
        
        # 将AI的响应添加到历史记录
        session.add_message(
            role="agent",
            content=planner_response.talk_to_player,
            msg_type=MessageType.CHAT,
            world_timestamp=batch.game_state.timestamp if batch.game_state else "000000"
        )
        
        # 如果有计划步骤，也添加到历史记录
        if planner_response.plan:
            plan_summary = "\n".join([f"- {plan.description}" for plan in planner_response.plan])
            session.add_message(
                role="agent",
                content=f"Plans:\n{plan_summary}",
                msg_type=MessageType.EVENT,
                world_timestamp=batch.game_state.timestamp if batch.game_state else "000000"
            )
        
        return planner_response
        
    except Exception as e:
        logger.error(f"Error in handle_events: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to handle events: {str(e)}")

"""
暂时不使用
@app.post("/texture/generate")
async def generate_texture(req: TextureJobRequest):

    贴图生成入口 - 简化版本，专注于核心参数，支持多面共用纹理
    直接生成贴图并返回结果
    
    参数说明：
    - req.voxel_name: 体素名称，用于标识这个纹理是给哪个voxel用的
    - req.faces: 要应用此纹理的面列表
    - req.pprompt: 正面提示词
    - req.nprompt: 负面提示词（可选）
    - req.reference_image: 参考图片文件名（可选，不需要完整路径）
    
    返回：
    - 生成的贴图文件名和应用的面信息

    try:
        logger.info(f"Received texture generation request: {req.dict()}")
        logger.info(f"Generating texture for voxel '{req.voxel_name}', faces: {[f.value for f in req.faces]}")
        logger.info(f"Prompt: {req.pprompt}")
        
        # 生成一张纹理，可以应用到多个面
        result = await texture_generator.generate_texture(
            tex_name=req.texture_name,
            pprompt=req.pprompt,
            nprompt=req.nprompt,
            reference_image=req.reference_image
        )
        
        logger.info(f"Generation completed. Generated texture: {result}")
        logger.info(f"This texture can be applied to faces: {[f.value for f in req.faces]}")
        
        return {
            "voxel_name": req.voxel_name,
            "texture_name": req.texture_name,
            "generated_texture_file": result,  # 一张纹理文件
            "success": bool(result)
        }
    except Exception as e:
        logger.error(f"Error in texture generation: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to generate texture: {str(e)}")

@app.post("/planner/test", response_model=PlannerTestResponse)
async def test_planner(batch: EventBatch):
    try:
        # 确保会话存在（会自动处理空的session_id）
        session = session_manager.get_or_create_session(batch.session_id)
        batch.session_id = session.session_id  # 更新batch中的session_id（如果是新生成的）
            
        logger.info(f"Testing planner with {len(batch.events)} events for session {batch.session_id}")
        
        # 处理事件批次，更新会话历史
        session = session_manager.process_event_batch(batch)
        logger.info(f"Session history updated, current message count: {len(session.conversation_history)}")
        
        # 使用Planner生成计划（batch包含所有需要的信息）
        result = await plan_async(batch)
        
        # 检查result结构
        if isinstance(result, dict) and "planner_response" in result:
            planner_response = result["planner_response"]
            debug_info = result["debug_info"]
            logger.info(f"Planner test completed. Talk: '{planner_response.talk_to_player[:50]}...', Plan steps: {len(planner_response.plan)}")
            
            # 将AI的响应添加到历史记录
            session.add_message(
                role="agent",
                content=planner_response.talk_to_player,
                msg_type=MessageType.CHAT,
                world_timestamp=batch.game_state.timestamp if batch.game_state else "000000"
            )
            
            # 如果有计划步骤，也添加到历史记录
            if planner_response.plan:
                plan_summary = "\n".join([f"- {plan.description}" for plan in planner_response.plan])
                session.add_message(
                    role="agent",
                    content=f"Plans:\n{plan_summary}",
                    msg_type=MessageType.EVENT,
                    world_timestamp=batch.game_state.timestamp if batch.game_state else "000000"
                )
            
            # 返回PlannerTestResponse格式
            return PlannerTestResponse(
                response=planner_response,
                debug_info=debug_info
            )
        else:
            # 错误情况
            logger.error("Unexpected result format from planner")
            raise HTTPException(500, "Invalid planner response format")
        
    except Exception as e:
        logger.error(f"Error in test_planner: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to test planner: {str(e)}")
"""

@app.post("/permission", response_model=CommandBatch)
async def handle_plan_permission(permission: PlanPermission):
    """
    处理计划许可，执行批准的计划
    
    接收Unity发送的计划许可，将批准的计划转换为具体的执行命令
    """
    try:
        logger.info(f"Received plan permission for session {permission.session_id}")
        logger.info(f"Goal: {permission.goal_label}")
        logger.info(f"Approved plans: {len(permission.approved_plans)}")
        
        # Log payload (omit heavy game_state to keep terminal output concise)
        permission_payload = permission.dict()
        if permission_payload.get("game_state") is not None:
            permission_payload["game_state"] = "[omitted]"
        logger.info(
            "Plan permission payload (no game_state):\n%s",
            json.dumps(permission_payload, ensure_ascii=False, indent=2),
        )
        
        # 处理计划许可，注册到会话管理器
        session_manager.process_plan_permission(permission)
        
        # 使用执行器将计划转换为命令
        command_batch = await executor.execute_plans(permission)
        
        logger.info(f"Generated {len(command_batch.commands)} commands")
        
        return command_batch
        
    except Exception as e:
        logger.error(f"Error in handle_plan_permission: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to handle plan permission: {str(e)}")

@app.post("/session/clear", response_model=SessionAck)
async def clear_session(req: SessionClearRequest):
    """
    清空会话
    清除聊天记录、世界状态缓存和待处理任务
    """
    try:
        if req.clear_all:
            session_manager.clear_all()
        else:
            session_manager.clear_session(req.session_id)
        return SessionAck(session_id=req.session_id, status="cleared")
    except Exception as e:
        return SessionAck(
            session_id=req.session_id,
            status="error",
            error=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)