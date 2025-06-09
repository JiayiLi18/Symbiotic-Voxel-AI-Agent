from fastapi import FastAPI, Form, Header, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import uvicorn
from datetime import datetime

# 导入核心功能
from core.tools.session.manager import SessionManager
from core.tools.session.analyzer import SessionAnalyzer
from core.tools.texture.texture_generator import TextureGenerator
from core.execute import ResponseExecutor
from core.prompts.system_prompt import generate_system_prompt
from core.models.session import Block, Position, MessageType

app = FastAPI()
session_manager = SessionManager()
session_analyzer = SessionAnalyzer()
texture_generator = TextureGenerator()
response_executor = ResponseExecutor()

# 启用CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ask")
async def ask(
    query: str = Form(...),
    image_path: Optional[str] = Form(None),
    session_id: Optional[str] = Header(None, alias="session-id"),
    new_session: bool = Form(False),
    blocks: Optional[List[Block]] = Body(None),
    player_position: Optional[Position] = Body(None)
):
    """处理聊天查询"""
    # 会话管理
    if not session_id or new_session:
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 获取或创建会话状态
    session_state = session_manager.get_or_create_session(session_id)
    
    # 如果提供了环境信息，更新环境状态
    if blocks is not None:
        session_state.add_environment_state(blocks, player_position)
    
    # 添加用户消息到聊天历史
    session_state.add_chat("user", query, image_path)
    
    # 分析查询，提取重要信息
    important_info = await session_analyzer.analyze_message(
        message=query,
        message_type=MessageType.CHAT,
        session_state=session_state
    )
    if important_info:
        session_manager.add_important_info(session_id, important_info)
    
    # 生成系统提示词（包含环境信息）
    system_prompt = generate_system_prompt(
        session_state=session_state,
        context={
            "query": query,
            "has_image": bool(image_path),
            "current_environment": session_state.environment_history[-1] if session_state.environment_history else None
        }
    )
    
    # 处理查询并获取响应
    response = await session_manager.process_message(
        session_id=session_id,
        message=query,
        system_prompt=system_prompt
    )
    
    # 执行响应中的命令
    result = await response_executor.execute_response(
        query=query,
        response_json=response,
        image_path=image_path
    )
    
    # 添加助手回复到聊天历史
    session_state.add_chat("assistant", result["data"]["answer"])
    
    return {
        "session_id": session_id,
        "response": result,
        "important_info": important_info
    }

@app.post("/sense")
async def sense(
    session_id: str = Header(...),
    blocks: List[Block] = Body(...),
    player_position: Optional[Position] = Body(None),
    action_type: Optional[str] = Body(None)  # 例如: "build", "destroy", "move"
):
    """处理环境感知信息"""
    session_state = session_manager.get_or_create_session(session_id)
    
    # 更新环境状态
    session_state.add_environment_state(blocks, player_position)
    
    # 分析环境变化，提取重要信息
    important_info = await session_analyzer.analyze_environment(
        blocks=blocks,
        player_position=player_position,
        action_type=action_type,
        session_state=session_state
    )
    
    if important_info:
        session_manager.add_important_info(session_id, important_info)
    
    return {
        "success": True,
        "session_id": session_id,
        "important_info": important_info
    }

@app.post("/texture/generate")
async def generate_texture(
    voxel_name: str = Form(""),
    positive_prompt: str = Form(...),
    negative_prompt: str = Form("text, blurry, watermark"),
    denoise_strength: float = Form(1.0),
):
    """贴图生成端点"""
    try:
        texture_path = await texture_generator.generate_texture(
            voxel_name=voxel_name,
            pprompt=positive_prompt,
            nprompt=negative_prompt,
            denoise=denoise_strength
        )
        return {
            "success": True,
            "texture_path": texture_path
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/session/clear")
async def clear_session(
    session_id: str = Header(...)
):
    """清除会话端点"""
    session_manager.clear_session(session_id)
    return {"message": "Session cleared successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)