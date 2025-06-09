# core/tools/execute.py
import json
from typing import Optional
from core.tools.voxel.modify import VoxelModifier
from core.tools.voxel.build import VoxelBuilder
from core.tools.texture.texture_generator import TextureGenerator
from core.tools.database.voxel_db import VoxelDB

class ResponseExecutor:
    def __init__(self):
        self.voxel_modifier = VoxelModifier("path/to/voxel.db")
        self.voxel_builder = VoxelBuilder()
        self.texture_generator = TextureGenerator()
        
    async def execute_response(self, query: str, response_json: str, image_path: Optional[str] = None) -> dict:
        """执行响应中的命令"""
        try:
            response_data = json.loads(response_json)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse response: {e}",
                "data": None
            }

        # 初始化响应结构
        response_payload = {
            "success": True,
            "error": None,
            "data": {
                "query": query,
                "answer": response_data.get("answer", ""),
                "commands": {
                    "textures": [],
                    "voxels": []
                }
            }
        }

        commands = response_data.get("commands", [])
        current_texture = None
        
        for command in commands:
            command_type = command.get("type")
            params = command.get("params", {})

            try:
                if command_type == "generate_texture":
                    texture_result = await self._handle_texture_generation(
                        image_path, 
                        params,
                        response_payload
                    )
                    current_texture = texture_result.get("texture_path")
                    
                elif command_type == "modify_voxel":
                    await self._handle_voxel_modification(
                        params,
                        current_texture,
                        response_payload
                    )
                    current_texture = None  # 重置当前贴图
                    
                elif command_type == "build_voxel":
                    await self._handle_voxel_building(
                        params,
                        response_payload
                    )

            except Exception as e:
                print(f"Error processing command {command_type}: {str(e)}")
                response_payload["data"]["commands"]["errors"].append({
                    "command": command_type,
                    "error": str(e)
                })

        return response_payload

    async def _handle_texture_generation(
        self, 
        image_path: str, 
        params: dict,
        response_payload: dict
    ) -> dict:
        """处理贴图生成命令"""
        result = {
            "executed": True,
            "success": False,
            "texture_path": None,
            "error": None
        }
        
        try:
            texture_path = await self.texture_generator.generate_texture(
                voxel_name=params.get("voxel_name", ""),
                pprompt=params.get("pprompt", ""),
                nprompt=params.get("nprompt", "text, blurry, watermark"),
                denoise=params.get("denoise", 1.0)
            )
            result.update({
                "success": True,
                "texture_path": texture_path
            })
        except Exception as e:
            result["error"] = str(e)
            
        response_payload["data"]["commands"]["textures"].append(result)
        return result

    async def _handle_voxel_modification(
        self, 
        params: dict,
        current_texture: Optional[str],
        response_payload: dict
    ) -> None:
        """处理Voxel修改命令"""
        result = {
            "executed": True,
            "success": False,
            "voxel_id": None,
            "error": None
        }
        
        try:
            if current_texture:
                params["texture"] = current_texture
            
            modified_voxel = await self.voxel_modifier.modify_voxel(params)
            result.update({
                "success": True,
                "voxel_id": modified_voxel["id"]
            })
        except Exception as e:
            result["error"] = str(e)
            
        response_payload["data"]["commands"]["voxels"].append(result)

    async def _handle_voxel_building(
        self, 
        params: dict,
        response_payload: dict
    ) -> None:
        """处理Voxel建造命令"""
        result = {
            "executed": True,
            "success": False,
            "error": None
        }
        
        try:
            await self.voxel_builder.build(params)
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)
            
        response_payload["data"]["commands"]["voxels"].append(result)