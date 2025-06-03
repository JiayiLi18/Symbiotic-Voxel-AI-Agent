from fastapi import FastAPI, File, UploadFile, Form, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import os, uvicorn, json

# Import core functionality
from tools.ask import call_openai_api
from tools.response_handler import ResponseHandler, encode_image_to_data_uri
from tools.session_manager import SessionManager

app = FastAPI()
response_handler = ResponseHandler()
session_manager = SessionManager()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ask_general")
async def ask_general(
    query: str = Form(...),
    image_path: Optional[str] = Form(None),
    session_id: Optional[str] = Header(None),
    new_session: bool = Form(False)
):
    """
    Main endpoint for handling general queries with optional image input
    Args:
        query: 用户的查询文本
        image_path: 可选的图片路径
        session_id: 会话ID（在header中）
        new_session: 是否开启新会话
    """
    # 处理会话ID
    if not session_id:
        return {"error": "Missing session_id in headers"}
    
    # 如果要求新会话，清除历史记录
    if new_session:
        session_manager.clear_session(session_id)
    
    # 获取历史记录
    conversation_history = session_manager.get_history(session_id)
    
    # Assemble conversation
    messages = [{"type": "text", "text": query}]
    if image_path and os.path.exists(image_path):
        try:
            messages.append({
                "type": "image_url",
                "image_url": encode_image_to_data_uri(image_path)
            })
        except Exception as e:
            return {"error": f"Failed to read image: {e}"}

    # Call GPT with conversation history
    try:
        response_json, usage = call_openai_api(
            messages,
            conversation_history=conversation_history
        )
        print(f"\nDEBUG - GPT Response JSON:\n{response_json}")
        
        # 添加新的对话到历史记录
        session_manager.add_message("user", "user", query)
        
        # 从response_json中提取assistant的回复并添加到历史记录
        try:
            response_data = json.loads(response_json)
            assistant_message = response_data.get("answer", response_json)
        except json.JSONDecodeError:
            assistant_message = response_json
        session_manager.add_message(session_id, "assistant", assistant_message)
        
    except Exception as e:
        return {"error": f"Failed to call GPT: {e}"}

    # Process response and execute commands
    return await response_handler.process_response(query, response_json, usage, image_path)

@app.post("/clear_session")
async def clear_session(session_id: str = Header(...)):
    """清除指定会话的历史记录"""
    session_manager.clear_session(session_id)
    return {"message": "Session cleared successfully"}

@app.post("/generate_texture")
async def generate_texture(
    image_path: str = Form(...),
    texture_name: str = Form(""),
    positive_prompt: str = Form(...),
    denoise_strength: float = Form(1.0),    
):
    """Standalone texture generation endpoint"""
    try:
        texture_path = await response_handler._handle_texture_generation(
            image_path,
            {
                "voxel_name": texture_name,
                "pprompt": positive_prompt,
                "denoise": denoise_strength
            }
        )
        return {
            "success": True,
            "texture_path": texture_path
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"生成贴图失败: {str(e)}"
        }

@app.post("/ask_test")
async def ask_test(
    query: str = Query(...), 
    image_path: str | None = Query(None),
    new_session: bool = Query(False)
):
    """
    Test endpoint that matches ask_general functionality but uses Query parameters
    and a fixed test session ID for easier testing
    """
    # 使用固定的测试会话ID
    TEST_SESSION_ID = "test_session"
    
    # 如果要求新会话，清除历史记录
    if new_session:
        session_manager.clear_session(TEST_SESSION_ID)
    
    # 获取历史记录
    conversation_history = session_manager.get_history(TEST_SESSION_ID)
    
    # Assemble conversation
    messages = [{"type": "text", "text": query}]
    if image_path and os.path.exists(image_path):
        try:
            messages.append({
                "type": "image_url",
                "image_url": encode_image_to_data_uri(image_path)
            })
        except Exception as e:
            return {"error": f"Failed to read image: {e}"}

    # Call GPT with conversation history
    try:
        response_json, usage = call_openai_api(
            messages,
            conversation_history=conversation_history
        )
        
        # 添加新的对话到历史记录
        session_manager.add_message(TEST_SESSION_ID, "user", query)
        
        # 从response_json中提取assistant的回复并添加到历史记录
        try:
            response_data = json.loads(response_json)
            assistant_message = response_data.get("answer", response_json)
        except json.JSONDecodeError:
            assistant_message = response_json
        session_manager.add_message(TEST_SESSION_ID, "assistant", assistant_message)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error details:\n{error_details}")
        return {"error": f"Failed to call GPT: {str(e)}"}

    # Process response and execute commands
    result = await response_handler.process_response(query, response_json, usage, image_path)
    
    # 为测试端点添加额外的调试信息
    result.update({
        "debug_info": {
            "session_id": TEST_SESSION_ID,
            "history_length": len(conversation_history),
            "current_history": conversation_history
        }
    })
    
    return result

@app.get("/test_history")
async def get_test_history():
    """
    获取测试会话的当前历史记录
    """
    TEST_SESSION_ID = "test_session"
    history = session_manager.get_history(TEST_SESSION_ID)
    return {
        "session_id": TEST_SESSION_ID,
        "history": history,
        "history_length": len(history)
    }

@app.post("/clear_test_session")
async def clear_test_session():
    """
    清除测试会话的历史记录
    """
    TEST_SESSION_ID = "test_session"
    session_manager.clear_session(TEST_SESSION_ID)
    return {"message": "Test session cleared successfully"}

@app.on_event("startup")
async def startup_event():
    """服务启动时的初始化"""
    # 可以添加定期清理过期会话的任务
    pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
