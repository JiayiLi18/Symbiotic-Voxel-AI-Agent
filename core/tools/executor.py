# core/tools/executor.py
"""
Executor - 将批准的计划转换为具体的执行命令
使用OpenAI API而非硬编码逻辑，遵循与planner相同的架构
"""

from typing import List, Dict, Any, Optional
from core.models.base import Plan, Command, GenerateTextureParams, VoxelType, CreateVoxelTypeParams, UpdateVoxelTypeParams
from core.models.protocol import PlanPermission, CommandBatch, SimpleExecutorResponse
from core.models.texture import VoxelFace, TextureJobRequest
from core.prompts.system_prompt import generate_executor_system_prompt
from core.schemas.openai_schemas import get_executor_response_schema
from core.tools.id_generator import new_command_id
from core.tools.texture.texture_generator import TextureGenerator
from core.tools.voxel.manager import VoxelManager
from core.tools.config import get_paths_config
import json
import asyncio
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
import logging

# 确保环境变量已加载
load_dotenv()

logger = logging.getLogger(__name__)

# 延迟初始化全局变量（避免导入时的环境变量问题）
openai_client = None
texture_generator = None
voxel_manager: Optional[VoxelManager] = None

def _ensure_initialized():
    """确保全局变量已初始化"""
    global openai_client, texture_generator, voxel_manager
    if openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Please set it in environment or .env file")
        
        openai_client = AsyncOpenAI(api_key=api_key)
    
    if texture_generator is None:
        texture_generator = TextureGenerator()
    
    if voxel_manager is None:
        cfg = get_paths_config()
        voxel_manager = VoxelManager(cfg.voxel_db_path)

class Executor:
    """执行器 - 将计划转换为具体命令，使用OpenAI API生成智能化的命令参数"""
    
    def __init__(self):
        pass
    
    async def execute_plans(self, permission: PlanPermission) -> CommandBatch:
        """
        执行批准的计划，转换为命令批次
        
        Args:
            permission: Unity返回的计划许可
            
        Returns:
            CommandBatch: 要发送给Unity的命令批次
        """
        try:
            # 直接调用异步方法
            result = await self._execute_plans_async(permission)
            return result
        except Exception as e:
            logger.error(f"Failed to execute plans: {str(e)}")
            # 返回空的命令批次作为fallback
            return CommandBatch(
                session_id=permission.session_id,
                goal_id=permission.goal_id,
                commands=[]
            )
    
    async def _execute_plans_async(self, permission: PlanPermission) -> CommandBatch:
        """异步执行计划转换"""
        
        # 确保所有全局变量已初始化
        _ensure_initialized()
        
        try:
            # 1. 生成系统提示词
            system_prompt = await generate_executor_system_prompt(permission)
            
            # 2. 调用OpenAI获取命令
            commands = await self._call_openai_for_commands(system_prompt, permission)
            
            # 3. 返回命令批次
            return CommandBatch(
                session_id=permission.session_id,
                goal_id=permission.goal_id,
                commands=commands
            )
            
        except Exception as e:
            import traceback
            error_details = f"Error in executor: {str(e)}\nTraceback: {traceback.format_exc()}"
            logger.error(error_details)
            
            # 兜底：返回空命令批次
            return CommandBatch(
                session_id=permission.session_id,
                goal_id=permission.goal_id,
                commands=[]
            )
    
    async def _call_openai_for_commands(self, system_prompt: str, permission: PlanPermission) -> List[Command]:
        """调用OpenAI生成命令"""
        
        # 构建用户消息 - 简洁地描述需要执行的计划
        user_message = "Convert the approved plans into executable commands."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            # 调用OpenAI API
            response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.1,       # 较低温度，确保输出稳定
                max_tokens=2000,
                response_format=get_executor_response_schema(strict=False),
                seed=42                # 可复现性
            )

            content = response.choices[0].message.content
            data = json.loads(content)
            
            # 解析SimpleExecutorResponse
            simple_response = SimpleExecutorResponse(**data)
            
            # 转换为完整的Command列表，生成命令ID
            commands = []
            for i, cmd_data in enumerate(simple_response.commands):
                try:
                    # 生成命令ID
                    command_id = new_command_id(permission.goal_id, i + 1)
                    
                    # 创建Command对象
                    command = Command(
                        id=command_id,
                        type=cmd_data.type,
                        params=cmd_data.params
                    )
                    
                    # 弃用：如果是纹理生成命令，直接执行纹理生成
                    #if command.type == "generate_texture":
                    #    await self._handle_texture_generation_command(command)
                    
                    # 体素类型：创建
                    if command.type == "create_voxel_type":
                        await self._handle_create_voxel_type_command(command)
                    
                    # 体素类型：更新
                    elif command.type == "update_voxel_type":
                        await self._handle_update_voxel_type_command(command)

                    # 参数富化：为place/destroy补全voxel_id等
                    await self._enrich_command_params(command)
                    
                    commands.append(command)
                    logger.info(f"Generated command {command.id} of type {command.type}")
                except Exception as e:
                    logger.error(f"Failed to parse command: {str(e)}")
                    continue
            
            return commands

        except Exception as e:
            import traceback
            error_details = f"OpenAI call failed: {str(e)}\nTraceback: {traceback.format_exc()}"
            logger.error(error_details)
            
            # 兜底：返回空命令列表
            return []
        

    async def _handle_create_voxel_type_command(self, command: Command):
        """处理创建体素类型命令：调用 VoxelManager.create_voxel"""
        try:
            _ensure_initialized()
            if not isinstance(command.params, CreateVoxelTypeParams):
                if isinstance(command.params, dict):
                    # 允许直接传完整 voxel_type 字典
                    voxel_type_data = command.params.get("voxel_type", command.params)
                    
                    # 如果没有id，生成一个基于名称的id
                    if "id" not in voxel_type_data and "name" in voxel_type_data:
                        voxel_type_data["id"] = voxel_type_data["name"].lower().replace(" ", "_")
                    
                    params = CreateVoxelTypeParams(voxel_type=VoxelType(**voxel_type_data))
                else:
                    logger.error(f"Invalid params type for create_voxel_type: {type(command.params)}")
                    return
            else:
                params = command.params

            assert voxel_manager is not None
            result = await voxel_manager.create_voxel(params)
            # 仅保留最终结果，避免重复回显原始params
            command.params = {"params": result}
        except Exception as e:
            logger.error(f"Error in create_voxel_type command {command.id}: {str(e)}", exc_info=True)

    async def _handle_update_voxel_type_command(self, command: Command):
        """处理更新体素类型命令：调用 VoxelManager.modify_voxel"""
        try:
            _ensure_initialized()
            if not isinstance(command.params, UpdateVoxelTypeParams):
                if isinstance(command.params, dict):
                    voxel_id = command.params.get("voxel_id")
                    new_voxel_type = command.params.get("new_voxel_type") or command.params.get("voxel_type")
                    if voxel_id is None or new_voxel_type is None:
                        logger.error("update_voxel_type requires 'voxel_id' and 'new_voxel_type'")
                        return
                    params = UpdateVoxelTypeParams(voxel_id=str(voxel_id), new_voxel_type=VoxelType(**new_voxel_type))
                else:
                    logger.error(f"Invalid params type for update_voxel_type: {type(command.params)}")
                    return
            else:
                params = command.params

            assert voxel_manager is not None
            result = await voxel_manager.modify_voxel(params)
            if isinstance(command.params, dict):
                command.params["result"] = result
        except Exception as e:
            logger.error(f"Error in update_voxel_type command {command.id}: {str(e)}", exc_info=True)
    
    def _sort_plans_by_dependency(self, plans: List[Plan]) -> List[Plan]:
        """根据依赖关系对计划进行拓扑排序"""
        # 简单实现：先执行没有依赖的，再执行有依赖的
        no_deps = [p for p in plans if not p.depends_on]
        with_deps = [p for p in plans if p.depends_on]
        
        # 更复杂的依赖排序可以后续优化
        return no_deps + with_deps

    async def _enrich_command_params(self, command: Command) -> None:
        """为命令参数做补全和规范化，例如根据名称补全voxel_id。"""
        try:
            if command.type not in ("place_block", "destroy_block"):
                return
            _ensure_initialized()
            assert voxel_manager is not None

            # 统一使用可变字典进行处理
            params_obj = command.params
            if not isinstance(params_obj, dict):
                # 将Pydantic对象转换为dict以便补全
                try:
                    params_obj = params_obj.model_dump()  # type: ignore[attr-defined]
                except Exception:
                    return

            # place_block: voxel_name -> voxel_id
            if command.type == "place_block":
                voxel_name = params_obj.get("voxel_name")
                voxel_id = params_obj.get("voxel_id")
                if voxel_name and (voxel_id is None or voxel_id == "" or voxel_id == 0):
                    try:
                        voxel = await voxel_manager.get_voxel_by_name(str(voxel_name))
                        if voxel and "id" in voxel:
                            params_obj["voxel_id"] = str(voxel["id"])
                    except Exception:
                        pass

                # 确保count默认值
                if "count" not in params_obj or not params_obj["count"]:
                    params_obj["count"] = 1

            # destroy_block: voxel_names -> voxel_ids
            elif command.type == "destroy_block":
                voxel_names = params_obj.get("voxel_names")
                voxel_ids = params_obj.get("voxel_ids")
                if isinstance(voxel_names, list) and (not isinstance(voxel_ids, list) or len(voxel_ids) == 0):
                    resolved_ids: List[str] = []
                    for name in voxel_names:
                        try:
                            voxel = await voxel_manager.get_voxel_by_name(str(name))
                            if voxel and "id" in voxel:
                                resolved_ids.append(str(voxel["id"]))
                        except Exception:
                            continue
                    if resolved_ids:
                        params_obj["voxel_ids"] = resolved_ids

                # 确保count默认值
                if "count" not in params_obj or not params_obj["count"]:
                    params_obj["count"] = 1

            # 回写规范化后的参数
            command.params = params_obj
        except Exception as e:
            logger.warning(f"Failed to enrich params for command {command.id}: {e}")
            
    """
    async def _handle_texture_generation_command(self, command: Command):
        try:
            # 确保纹理生成器已初始化
            _ensure_initialized()
            
            # 获取命令参数
            if not isinstance(command.params, GenerateTextureParams):
                # 如果参数是字典，尝试转换为GenerateTextureParams
                if isinstance(command.params, dict):
                    params = GenerateTextureParams(**command.params)
                else:
                    logger.error(f"Invalid params type for generate_texture command: {type(command.params)}")
                    return
            else:
                params = command.params
            
            logger.info(f"Executing texture generation for command {command.id}")
            logger.info(f"Voxel: {params.voxel_name}, Faces: {[f.value if isinstance(f, VoxelFace) else f for f in params.faces]}")
            logger.info(f"Prompt: {params.pprompt}")
            
            # 转换面参数列表
            faces = []
            if isinstance(params.faces, list):
                for face_item in params.faces:
                    try:
                        if isinstance(face_item, VoxelFace):
                            faces.append(face_item)
                        else:
                            faces.append(VoxelFace.from_str(str(face_item)))
                    except ValueError:
                        logger.warning(f"Invalid face value: {face_item}, skipping")
            
            if not faces:
                faces = [VoxelFace.FRONT, VoxelFace.BACK, VoxelFace.LEFT, VoxelFace.RIGHT, VoxelFace.TOP, VoxelFace.BOTTOM]  # 默认使用所有面
                logger.info("No valid faces found, using front face as default")
            
            # 使用 property 生成纹理名称
            tex_name = params.texture_name
            logger.info(f"Generated texture name: {tex_name}")
            
            # 调用纹理生成器 - 生成一张纹理，可以应用到多个面
            result = await texture_generator.generate_texture(
                tex_name=tex_name,
                pprompt=params.pprompt,
                nprompt=params.nprompt,
                reference_image=params.reference_image
            )
            
            if result:
                logger.info(f"Texture generation completed successfully for command {command.id}")
                logger.info(f"Generated texture: {result}")
                logger.info(f"This texture can be applied to faces: {[f.value for f in faces]}")
                
                # 更新命令参数，添加生成结果信息
                if isinstance(command.params, dict):
                    command.params['generated_texture_file'] = result  # 一张纹理文件
                    command.params['texture_name'] = tex_name
                    command.params['applied_faces'] = [f.value for f in faces]  # 这张纹理可以应用的面
                else:
                    # 如果是GenerateTextureParams对象，添加结果字段
                    setattr(command.params, 'generated_texture_file', result)
                    setattr(command.params, 'texture_name', tex_name)
                    setattr(command.params, 'applied_faces', [f.value for f in faces])
            else:
                logger.warning(f"Texture generation failed for command {command.id}")
                
        except Exception as e:
            logger.error(f"Error in texture generation command {command.id}: {str(e)}", exc_info=True)
        """

# 创建全局执行器实例
executor = Executor()