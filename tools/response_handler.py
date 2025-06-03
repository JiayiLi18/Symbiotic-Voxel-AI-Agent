import json
import re
import base64
import os
import asyncio
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from .comfyUIHandler import call_comfyUI
from .voxel_manager import VoxelManager, VoxelTypeParams

def encode_image_to_data_uri(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

class ResponseHandler:
    def __init__(self):
        self.voxel_db_path = r"C:\Users\55485\AppData\LocalLow\DefaultCompany\AI-Agent\VoxelsDB\voxel_definitions.json"
        self.voxel_manager = VoxelManager(self.voxel_db_path)

    async def process_response(self, query: str, response_json: str, usage: dict, image_path: Optional[str] = None) -> dict:
        """Process GPT response and execute commands"""
        try:
            response_data = json.loads(response_json)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse GPT response: {e}",
                "data": None
            }

        # Initialize response structure
        response_payload = {
            "success": True,
            "error": None,
            "data": {
                "session_id": response_data.get("session_id", ""),
                "query": query,
                "answer": response_data.get("answer", ""),
                "token_usage": usage,
                "commands": {
                    "texture": {
                        "executed": False,
                        "success": False,
                        "texture_path": None,
                        "error": None
                    },
                    "voxel": {
                        "executed": False,
                        "success": False,
                        "voxel_id": None,
                        "voxel_name": None,
                        "texture_path": None,
                        "error": None,
                        "operation": None  # 'create' or 'update'
                    }
                }
            }
        }

        commands = response_data.get("commands", [])
        print(f"\nDEBUG - Processing {len(commands)} commands")
        
        # First, process texture generation if it exists
        texture_name = None
        for command in commands:
            if command.get("type") == "generate_texture":
                try:
                    response_payload["data"]["commands"]["texture"]["executed"] = True
                    texture_name = await self._handle_texture_generation(image_path, command.get("params", {}))
                    if texture_name and not texture_name.endswith(".png"):
                        texture_name = f"{texture_name}.png"
                    response_payload["data"]["commands"]["texture"].update({
                        "success": True,
                        "texture_path": texture_name
                    })
                except Exception as e:
                    error_msg = f"Error in generate_texture: {str(e)}"
                    print(f"DEBUG - {error_msg}")
                    response_payload["data"]["commands"]["texture"]["error"] = error_msg
                break  # Only process the first texture command

        # Then process other commands
        for command in commands:
            command_type = command.get("type")
            if command_type == "generate_texture":
                continue  # Skip as we've already processed it

            params = command.get("params", {})
            print(f"\nDEBUG - Processing command: {command_type}")
            print(f"DEBUG - Command params: {params}")

            try:
                if command_type == "create_voxel_type":
                    response_payload["data"]["commands"]["voxel"]["executed"] = True
                    # 使用VoxelManager创建voxel
                    voxel_params = VoxelTypeParams(
                        name=params.get("name"),
                        description=params.get("description", ""),
                        texture=texture_name or "",
                        is_transparent=params.get("is_transparent", False)
                    )
                    new_voxel = self.voxel_manager.create_voxel_type(voxel_params)
                    response_payload["data"]["commands"]["voxel"].update({
                        "success": True,
                        "voxel_id": new_voxel["id"],
                        "voxel_name": new_voxel["name"],
                        "texture_path": texture_name,
                        "operation": "create"
                    })
                elif command_type == "update_voxel_type":
                    response_payload["data"]["commands"]["voxel"]["executed"] = True
                    # 使用VoxelManager更新voxel
                    voxel_name = params.get("name")
                    voxel = self.voxel_manager.get_voxel_by_name(voxel_name)
                    voxel_id = voxel["id"] if voxel else None
                    
                    if voxel_id:
                        update_params = {}
                        if texture_name:
                            update_params["texture"] = texture_name
                        if "description" in params:
                            update_params["description"] = params["description"]
                        if "is_transparent" in params:
                            update_params["is_transparent"] = params["is_transparent"]
                        
                        updated_voxel = self.voxel_manager.update_voxel_type(voxel_id, update_params)
                        if updated_voxel:
                            response_payload["data"]["commands"]["voxel"].update({
                                "success": True,
                                "voxel_id": updated_voxel["id"],
                                "voxel_name": updated_voxel["name"],
                                "texture_path": texture_name,
                                "operation": "update"
                            })
                        else:
                            response_payload["data"]["commands"]["voxel"]["error"] = f"Failed to update voxel with ID {voxel_id}"
                    else:
                        response_payload["data"]["commands"]["voxel"]["error"] = f"Voxel with name '{voxel_name}' not found"

            except Exception as e:
                error_msg = f"Error in {command_type}: {str(e)}"
                print(f"DEBUG - {error_msg}")
                if command_type in ["create_voxel_type", "update_voxel_type"]:
                    response_payload["data"]["commands"]["voxel"]["error"] = error_msg

        return response_payload

    async def _handle_texture_generation(self, image_path: str, params: dict) -> str:
        """Handle texture generation command"""
        print("DEBUG - Generating texture...")
        texture_name = await asyncio.to_thread(
            call_comfyUI,
            image_path,
            params.get("voxel_name", ""),
            params.get("pprompt", ""),
            params.get("nprompt", "text, blurry, watermark"),
            params.get("denoise", 1.0)
        )
        print(f"DEBUG - Generated texture name: {texture_name}")
        return texture_name

# Test response parsing functions
def need_generate_texture(answer: str) -> bool:
    """Check if texture generation is needed"""
    print("DEBUG: Checking if texture generation is needed")
    
    try:
        json_str = answer[answer.find("{"):answer.rfind("}")+1]
        data = json.loads(json_str)
        if "generate_texture" in data:
            return True
    except Exception as e:
        print(f"DEBUG: JSON parsing failed: {e}")
    
    return "[[GENERATE_TEXTURE]]" in answer

def parse_texture_params(answer: str, input_image_path: str = "") -> dict:
    """Parse texture parameters from GPT response"""
    print("DEBUG: Parsing texture parameters")
    
    try:
        json_str = answer[answer.find("{"):answer.rfind("}")+1]
        data = json.loads(json_str)
        
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
    
    pattern = r"\[\[TEXTURE\]\](.*?)\[\[/TEXTURE\]\]"
    m = re.search(pattern, answer, re.S | re.I)
    if not m:
        return {}
    
    block = m.group(1)
    params = dict(re.findall(r"(\w+)\s*=\s*(.+)", block))
    
    return {
        "input_image": input_image_path,
        "pprompt": params.get("pprompt", ""),
        "nprompt": params.get("nprompt", ""),
        "denoise": float(params.get("denoise", 1) or 1),
    }

def need_fill_db(answer: str) -> bool:
    """Check if database fill is needed"""
    return "[[FILL_DB]]" in answer 

def parse_fill_content(answer: str) -> Tuple[str, str]:
    """Parse fill content from GPT response"""
    pattern = r"\[\[FILL\]\](.*?)\[\[/FILL\]\]"
    m = re.search(pattern, answer, re.S | re.I)
    if not m:
        return "", ""
    block = m.group(1)
    params = dict(re.findall(r"(\w+)\s*=\s*(.+)", block))
    return params.get("section", ""), params.get("content", "")

def need_create_voxel_type(answer: str) -> bool:
    """Check if voxel type creation is needed"""
    print("DEBUG: Checking if voxel type creation is needed")
    try:
        json_str = answer[answer.find("{"):answer.rfind("}")+1]
        data = json.loads(json_str)
        if "create_voxel_type" in data:
            return True
    except Exception as e:
        print(f"DEBUG: JSON parsing failed: {e}")
    
    pattern = r'{\s*"command"\s*:\s*"create_voxel_type".*?}'
    match = re.search(pattern, answer, re.DOTALL)
    return bool(match)

def parse_voxel_type_data(answer: str) -> dict:
    """Parse voxel type data from GPT response"""
    print("DEBUG: Parsing voxel type data")
    try:
        pattern = r'({[\s\S]*?"command"\s*:\s*"create_voxel_type"[\s\S]*?})'
        match = re.search(pattern, answer, re.DOTALL)
        if not match:
            return {}
        
        json_str = match.group(1)
        data = json.loads(json_str)
        if data.get("command") == "create_voxel_type":
            return data
    except Exception as e:
        print(f"DEBUG: Error parsing voxel data: {e}")
    return {} 