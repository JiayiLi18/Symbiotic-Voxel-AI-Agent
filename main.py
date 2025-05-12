from fastapi import FastAPI, File, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Union, Optional
import base64, os, uvicorn, re, asyncio
import json

# Assuming the query function is defined in ask.py, here's an example wrapper
from ask import call_openai_api
# Database filling function from fill_db.py
from fill_db import process_documents
# connect with comfyUI
from comfyUIHandler import call_comfyUI

app = FastAPI()

# Enable CORS to facilitate Unity client calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 整合接口 ----------

@app.post("/ask_general")
async def ask_general(
    query: str = Form(...),
    image_path: Optional[str] = Form(None)
):
    """
    一次搞定：
      1. 拼装文字 + 可选图片给 GPT
      2. 根据 GPT 回复决定要不要生成贴图、要不要写数据库
      3. 把所有结果打包回 Unity
    """
    # 1) 组装对话
    messages: list[dict] = [{"type": "text", "text": query}]
    if image_path and os.path.exists(image_path):
        try:
            messages.append({
                "type": "image_url",
                "image_url": encode_image_to_data_uri(image_path)
            })
        except Exception as e:
            return {"error": f"读取图片失败: {e}"}

    # 2) 调 GPT
    try:
        answer, usage = call_openai_api(messages)
    except Exception as e:
        return {"error": f"调用 GPT 失败: {e}"}

    response_payload = {
        "query": query,
        "answer": answer,
        "token_usage": usage,
        "generated_texture": None,
        "fill_db_result": None
    }

    # 3) 是否生成贴图
    if need_generate_texture(answer):
        tex_params = parse_texture_params(answer)
        if tex_params.get("pprompt"):  # 有pprompt才调用
            try:
                texture_path = await asyncio.to_thread(
                    call_comfyUI,
                    image_path,
                    "",
                    tex_params["pprompt"],
                    tex_params["nprompt"],
                    tex_params["denoise"]
                )
                response_payload["generated_texture"] = texture_path
            except Exception as e:
                response_payload["generated_texture"] = f"生成贴图失败: {e}"

    # 4) 是否写数据库
    if need_fill_db(answer):
        section, content = parse_fill_content(answer)
        if section and content:
            try:
                fill_result = await asyncio.to_thread(
                    process_documents,
                    section=section,
                    content=content
                )
                response_payload["fill_db_result"] = fill_result
            except Exception as e:
                response_payload["fill_db_result"] = f"写入失败: {e}"

    return response_payload

@app.post("/generate_texture")
async def generate_texture(
    image_path: str = Form(...),
    texture_name: str = Form(""),
    positive_prompt: str = Form(...),
    denoise_strength: float = Form(1.0),    
):
    """
    单独的贴图生成接口，只处理贴图生成功能
    
    Parameters:
    - image_path: 输入图片路径
    - positive_prompt: 正面提示词
    - negative_prompt: 负面提示词，默认为"text"
    - denoise_strength: 降噪强度，范围0-1，默认为1.0
    - texture_name: 纹理名称，默认为空字符串
    
    Returns:
    - success: 是否成功
    - texture_path: 成功时返回生成的贴图路径
    - error: 失败时返回错误信息
    """
    try:
        texture_path = await asyncio.to_thread(
            call_comfyUI,
            image_path,
            texture_name,
            positive_prompt,
            "text, blurry, watermark",
            denoise_strength
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

# ---------- 测试接口 ----------

@app.post("/ask_test")
async def ask_test(
    query: str = Query(...), 
    image_path: str | None = Query(None)
):
    """
    Test interface that matches ask_general functionality but uses Query parameters instead of Form.
    """
    # 1) 组装对话
    messages: list[dict] = [{"type": "text", "text": query}]
    if image_path and os.path.exists(image_path):
        try:
            messages.append({
                "type": "image_url",
                "image_url": encode_image_to_data_uri(image_path)
            })
        except Exception as e:
            return {"error": f"读取图片失败: {e}"}

    # 2) 调 GPT
    try:
        answer, usage = call_openai_api(messages)
    except Exception as e:
        return {"error": f"调用 GPT 失败: {e}"}

    response_payload = {
        "query": query,
        "answer": answer,
        "token_usage": usage,
        "generated_texture": None,
        "fill_db_result": None
    }

    # 3) 是否生成贴图
    if need_generate_texture(answer):
        tex_params = parse_texture_params(answer)
        if tex_params.get("pprompt"):  # 有pprompt才调用
            try:
                texture_path = await asyncio.to_thread(
                    call_comfyUI,
                    image_path,
                    "",
                    tex_params["pprompt"],
                    tex_params["nprompt"],
                    tex_params["denoise"]
                )
                response_payload["generated_texture"] = texture_path
            except Exception as e:
                response_payload["generated_texture"] = f"生成贴图失败: {e}"

    # 4) 是否写数据库
    if need_fill_db(answer):
        section, content = parse_fill_content(answer)
        if section and content:
            try:
                fill_result = await asyncio.to_thread(
                    process_documents,
                    section=section,
                    content=content
                )
                response_payload["fill_db_result"] = fill_result
            except Exception as e:
                response_payload["fill_db_result"] = f"写入失败: {e}"

    return response_payload

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    

# ---------- 工具函数 ----------
def encode_image_to_data_uri(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    # 这里只按 png 写，若有多格式需要自己判断
    return f"data:image/png;base64,{b64}"

def need_generate_texture(answer: str) -> bool:
    """检查是否需要生成贴图"""
    print("DEBUG: Checking if texture generation is needed")
    print(f"DEBUG: Answer contains [[GENERATE_TEXTURE]]: {'[[GENERATE_TEXTURE]]' in answer}")
    # 检查是否包含 JSON 格式的响应
    if "[[GENERATE_TEXTURE]]" in answer:
        try:
            # 尝试从 JSON 字符串中提取
            json_str = answer[answer.find("{"):answer.rfind("}")+1]
            data = json.loads(json_str)
            print(f"DEBUG: Found JSON data: {data}")
            return True
        except Exception as e:
            print(f"DEBUG: JSON parsing failed: {e}")
    return "[[GENERATE_TEXTURE]]" in answer

def parse_texture_params(answer: str, input_image_path: str = "") -> dict:
    """
    从 GPT 回复里抓出贴图参数，支持两种格式：
    1. 直接标记格式：
       [[TEXTURE]]
       pprompt=Texture of glass marble 
       nprompt=text, blurry, watermark
       denoise=1
       [[/TEXTURE]]
    
    2. JSON 格式：
       {
         "[[GENERATE_TEXTURE]]": {
           "[[TEXTURE]]": {
             "pprompt": "Texture of a flower",
             "nprompt": "text, blurry, watermark",
             "denoise": 0.85
           }
         }
       }
    """
    print("DEBUG: Parsing texture parameters")
    print(f"DEBUG: Original answer: {answer}")
    
    # 尝试 JSON 格式解析
    try:
        json_str = answer[answer.find("{"):answer.rfind("}")+1]
        data = json.loads(json_str)
        print(f"DEBUG: Parsed JSON data: {data}")
        
        # 提取参数
        if "[[GENERATE_TEXTURE]]" in data:
            texture_data = data["[[GENERATE_TEXTURE]]"]["[[TEXTURE]]"]
            return {
                "input_image": input_image_path,
                "pprompt": texture_data.get("pprompt", ""),
                "nprompt": texture_data.get("nprompt", ""),
                "denoise": float(texture_data.get("denoise", 1) or 1),
            }
    except Exception as e:
        print(f"DEBUG: JSON parsing failed: {e}")
    
    # 如果 JSON 解析失败，尝试直接标记格式
    pattern = r"\[\[TEXTURE\]\](.*?)\[\[/TEXTURE\]\]"
    m = re.search(pattern, answer, re.S | re.I)
    if not m:
        print("DEBUG: No texture parameters found in direct format")
        return {}
    
    block = m.group(1)
    params = dict(re.findall(r"(\w+)\s*=\s*(.+)", block))
    print(f"DEBUG: Found parameters in direct format: {params}")
    
    return {
        "input_image": input_image_path,
        "pprompt": params.get("pprompt", ""),
        "nprompt": params.get("nprompt", ""),
        "denoise": float(params.get("denoise", 1) or 1),
    }

def need_fill_db(answer: str) -> bool:
    """出现 [[FILL_DB]] 标记，需要根据后续情况修改"""
    return "[[FILL_DB]]" in answer 

def parse_fill_content(answer: str) -> tuple[str, str]:
    """
    从 GPT 回复里抓出要写库的 section 和 content，示例标记：
       [[FILL]]
       section=monsters
       content=火焰恶魔：弱点是冰冷武器...
       [[/FILL]]
       根据后续情况修改
    """
    pattern = r"\[\[FILL\]\](.*?)\[\[/FILL\]\]"
    m = re.search(pattern, answer, re.S | re.I)
    if not m:
        return "", ""
    block = m.group(1)
    params = dict(re.findall(r"(\w+)\s*=\s*(.+)", block))
    return params.get("section", ""), params.get("content", "")
