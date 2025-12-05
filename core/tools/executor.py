# core/tools/executor.py
"""
Executor - 将批准的计划转换为具体的执行命令
使用OpenAI API而非硬编码逻辑，遵循与planner相同的架构
"""

from typing import List, Dict, Any, Optional
from core.models.base import Plan, Command, GenerateTextureParams, VoxelType, CreateVoxelTypeParams, UpdateVoxelTypeParams
from core.models.protocol import PlanPermission, CommandBatch, SimpleExecutorResponse
from pydantic import ValidationError
from core.models.texture import VoxelFace, TextureJobRequest
from core.prompts.system_prompt import generate_executor_system_prompt
from core.schemas.openai_schemas import get_executor_response_schema
from core.tools.id_generator import new_command_id
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

def _ensure_initialized():
    """确保全局变量已初始化"""
    global openai_client
    if openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Please set it in environment or .env file")
        
        openai_client = AsyncOpenAI(api_key=api_key)

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

        # 没有批准的计划时，根据是否有 additional_info 决定行为
        if not permission.approved_plans:
            if permission.additional_info:
                # 玩家提供了反馈，生成 continue_plan 命令让 planner 重新规划
                logger.info(
                    "No approved plans for goal '%s', but player provided feedback. Generating continue_plan command.",
                    permission.goal_label,
                )
                logger.info("Player feedback: %s", permission.additional_info)
                
                from core.models.base import ContinuePlanParams
                continue_cmd = Command(
                    id=new_command_id(permission.goal_id, 1),
                    type="continue_plan",
                    params=ContinuePlanParams(
                        current_summary=f"Player rejected all plans for '{permission.goal_label}'.",
                        possible_next_steps=permission.additional_info,
                        request_snapshot=False
                    )
                )
                return CommandBatch(
                    session_id=permission.session_id,
                    goal_id=permission.goal_id,
                    commands=[continue_cmd]
                )
            else:
                # 没有反馈，直接返回空命令
                logger.info(
                    "No approved plans for goal '%s' and no feedback. Returning empty command batch.",
                    permission.goal_label,
                )
                return CommandBatch(
                    session_id=permission.session_id,
                    goal_id=permission.goal_id,
                    commands=[]
                )
        
        try:
            # 1. 生成系统提示词
            logger.info("Generating executor context...")
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
        
        MAX_RETRIES = 3
        
        for attempt in range(MAX_RETRIES):
            try:
                if attempt > 0:
                    logger.info(f"Retrying OpenAI call (Attempt {attempt + 1}/{MAX_RETRIES})...")
                
                # 调用OpenAI API
                # Note: reasoning parameter is only available in /v1/responses endpoint, not in /v1/chat/completions
                # If you need reasoning, consider switching to Responses API when SDK supports it
                response = await openai_client.chat.completions.create(
                    model="gpt-5-mini",
                    messages=messages,
                    max_completion_tokens=8000,
                    response_format=get_executor_response_schema(strict=False),
                )
                
                logger.info("Executor LLM response received.")

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
                        
                        # Note: create_voxel_type and update_voxel_type commands are sent to Unity as-is.
                        # Python executor does NOT modify voxel definitions - Unity handles all voxel modifications.
                        # The commands are just instructions, not direct database operations.

                        # 参数富化：为place/destroy补全voxel_id等（使用Unity传来的voxel_definitions）
                        await self._enrich_command_params(command, permission.game_state)
                        
                        commands.append(command)
                        logger.info(f"Generated command {command.id} of type {command.type}")
                    except Exception as e:
                        logger.error(f"Failed to parse command: {str(e)}")
                        continue
                
                return commands

            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning(f"Validation Error or JSON Error: {e}")
                if attempt < MAX_RETRIES - 1:
                    logger.info("Retrying...")
                    continue
                else:
                    logger.error("Max retries reached for validation errors.")
                    raise e
            except Exception as e:
                import traceback
                error_details = f"OpenAI call failed: {str(e)}\nTraceback: {traceback.format_exc()}"
                logger.error(error_details)
                
                # 兜底：返回空命令列表
                return []
        
        return []
        

    # Removed: _handle_create_voxel_type_command and _handle_update_voxel_type_command
    # Python executor should NOT modify voxel definitions - Unity handles all voxel modifications.
    # Commands are just instructions sent to Unity, not direct database operations.
    
    def _sort_plans_by_dependency(self, plans: List[Plan]) -> List[Plan]:
        """根据依赖关系对计划进行拓扑排序"""
        # 简单实现：先执行没有依赖的，再执行有依赖的
        no_deps = [p for p in plans if not p.depends_on]
        with_deps = [p for p in plans if p.depends_on]
        
        # 更复杂的依赖排序可以后续优化
        return no_deps + with_deps

    async def _enrich_command_params(self, command: Command, game_state=None) -> None:
        """为命令参数做补全和规范化，例如根据名称补全voxel_id。
        
        优先使用Unity传来的voxel_definitions，确保id和name的一致性。
        """
        try:
            if command.type not in ("place_block", "destroy_block"):
                return
            
            # 统一使用可变字典进行处理
            params_obj = command.params
            if not isinstance(params_obj, dict):
                # 将Pydantic对象转换为dict以便补全
                try:
                    params_obj = params_obj.model_dump()  # type: ignore[attr-defined]
                except Exception:
                    return

            # 使用Unity传来的voxel_definitions（Unity应该总是提供）
            voxel_definitions = None
            if game_state and game_state.voxel_definitions:
                voxel_definitions = game_state.voxel_definitions
            else:
                logger.warning("No voxel definitions available from Unity game_state for enrichment")
                return

            if not voxel_definitions:
                logger.warning("No voxel definitions available for enrichment")
                return

            # 构建name->id映射
            name_to_id_map = {}
            for voxel in voxel_definitions:
                if isinstance(voxel, dict):
                    name = voxel.get('name', '').lower()
                    voxel_id = voxel.get('id')
                    if name and voxel_id is not None:
                        name_to_id_map[name] = str(voxel_id)

            # place_block: voxel_name -> voxel_id
            if command.type == "place_block":
                voxel_name = params_obj.get("voxel_name")
                voxel_id = params_obj.get("voxel_id")
                if voxel_name and (voxel_id is None or voxel_id == "" or voxel_id == 0):
                    voxel_name_lower = str(voxel_name).lower()
                    if voxel_name_lower in name_to_id_map:
                        params_obj["voxel_id"] = name_to_id_map[voxel_name_lower]

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
                        name_lower = str(name).lower()
                        if name_lower in name_to_id_map:
                            resolved_ids.append(name_to_id_map[name_lower])
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