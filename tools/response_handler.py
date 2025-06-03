import json
import re
import base64
import os
import asyncio
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from .comfyUIHandler import call_comfyUI
from .fill_db import process_documents

def encode_image_to_data_uri(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

class ResponseHandler:
    def __init__(self):
        self.voxel_db_path = r"C:\Users\55485\AppData\LocalLow\DefaultCompany\AI-Agent\VoxelsDB\voxel_definitions.json"

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
                        "error": None
                    },
                    "database": {
                        "executed": False,
                        "success": False,
                        "section": None,
                        "error": None
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
                    # Use the texture_name we got from the previous texture generation
                    voxel_result = await self._handle_voxel_creation(
                        params, 
                        texture_name
                    )
                    voxel_info = self._parse_voxel_result(voxel_result)
                    response_payload["data"]["commands"]["voxel"].update({
                        "success": True,
                        "voxel_id": voxel_info["id"],
                        "voxel_name": voxel_info["name"],
                        "texture_path": texture_name
                    })

                elif command_type == "fill_db":
                    response_payload["data"]["commands"]["database"]["executed"] = True
                    section = params.get("section", "")
                    fill_result = await self._handle_db_fill(params)
                    response_payload["data"]["commands"]["database"].update({
                        "success": True,
                        "section": section
                    })

            except Exception as e:
                error_msg = f"Error in {command_type}: {str(e)}"
                print(f"DEBUG - {error_msg}")
                if command_type == "create_voxel_type":
                    response_payload["data"]["commands"]["voxel"]["error"] = error_msg
                elif command_type == "fill_db":
                    response_payload["data"]["commands"]["database"]["error"] = error_msg

        return response_payload

    def _parse_voxel_result(self, result: str) -> dict:
        """Parse voxel creation result string to extract ID and name"""
        try:
            # Expected format: "Successfully created voxel type: {name} (ID: {id})"
            match = re.search(r"Successfully created voxel type: (.*?) \(ID: (\d+)\)", result)
            if match:
                name = match.group(1)
                voxel_id = int(match.group(2))
                
                # Read the voxel from database to get complete info
                try:
                    with open(self.voxel_db_path, 'r') as f:
                        voxel_db = json.load(f)
                        for voxel in voxel_db.get("voxels", []):
                            if voxel["id"] == voxel_id:
                                return {
                                    "name": name,
                                    "id": voxel_id,
                                    "texture": voxel.get("texture", "")
                                }
                except Exception as e:
                    print(f"Warning: Could not read voxel database: {e}")
                
                return {
                    "name": name,
                    "id": voxel_id,
                    "texture": ""
                }
            return {"name": None, "id": None, "texture": None}
        except Exception:
            return {"name": None, "id": None, "texture": None}

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

    async def _handle_voxel_creation(self, params: dict, texture_name: str) -> str:
        """Handle voxel type creation command"""
        print("DEBUG - Creating voxel type...")
        # Ensure texture_name has .png extension
        if texture_name and not texture_name.endswith(".png"):
            texture_name = f"{texture_name}.png"
            
        voxel_params = {
            "displayName": params.get("name"),
            "baseColor": params.get("base_color", "#FFFFFF"),
            "description": params.get("description", ""),
            "texture": texture_name  # Pass texture name to voxel creation
        }
        print(f"DEBUG - Voxel params: {voxel_params}")
        return await asyncio.to_thread(
            self._create_voxel_type,
            voxel_params,
            texture_name
        )

    async def _handle_db_fill(self, params: dict) -> str:
        """Handle database fill command"""
        print("DEBUG - Filling database...")
        return await asyncio.to_thread(
            process_documents,
            section=params.get("section"),
            content=params.get("content")
        )

    def _create_voxel_type(self, voxel_data: dict, texture_name: Optional[str] = None) -> str:
        """Create new voxel type and update JSON file"""
        print(f"DEBUG: Creating voxel type: {voxel_data}")
        print(f"DEBUG: Texture name: {texture_name}")
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.voxel_db_path), exist_ok=True)
            
            # Read existing voxel definitions
            voxel_db = self._read_or_create_voxel_db()
            
            # Find max ID and create new voxel entry
            next_voxel_id = self._get_next_voxel_id(voxel_db)
            new_voxel = self._create_voxel_entry(next_voxel_id, voxel_data, texture_name)
            
            # Add new voxel and update database
            voxel_db["voxels"].append(new_voxel)
            voxel_db["revision"] = datetime.utcnow().isoformat("T") + "Z"
            
            # Save updated definitions
            with open(self.voxel_db_path, 'w') as f:
                json.dump(voxel_db, f, indent=4)
                
            return f"Successfully created voxel type: {new_voxel['name']} (ID: {next_voxel_id})"
        
        except Exception as e:
            print(f"ERROR: Failed to create voxel type: {e}")
            raise Exception(f"Failed to create voxel type: {e}")

    def _read_or_create_voxel_db(self) -> dict:
        """Read existing voxel database or create new one"""
        if os.path.exists(self.voxel_db_path):
            with open(self.voxel_db_path, 'r') as f:
                return json.load(f)
        return {
            "next_id": 0,
            "revision": datetime.utcnow().isoformat("T") + "Z",
            "voxels": []
        }

    def _get_next_voxel_id(self, voxel_db: dict) -> int:
        """Get next available voxel ID"""
        max_id = -1
        for voxel in voxel_db.get("voxels", []):
            if "id" in voxel and voxel["id"] > max_id:
                max_id = voxel["id"]
        return max_id + 1

    def _create_voxel_entry(self, voxel_id: int, voxel_data: dict, texture_name: Optional[str]) -> dict:
        """Create new voxel entry"""
        # Parse color
        hex_color = voxel_data.get("baseColor", "#FFFFFF")
        if hex_color.startswith("#"):
            hex_color = hex_color[1:]
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Handle display name
        display_name = voxel_data.get("displayName", "Unknown")
        if display_name.lower() == "unknown" or not display_name:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            display_name = f"Unknown_{timestamp}"
        
        # Process texture name - use the one from voxel_data if available
        texture_field = voxel_data.get("texture", "")
        if not texture_field and texture_name:
            texture_field = texture_name
        
        return {
            "id": voxel_id,
            "name": display_name,
            "texture": texture_field,
            "face_textures": ["", "", "", "", "", ""],
            "base_color": [r, g, b],
            "description": voxel_data.get("description", ""),
            "is_transparent": False
        }

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