# core/tools/session/converter.py
"""
简化的Unity原始数据到SessionState转换器
只保留核心对话历史，过滤不必要信息
"""

from typing import Dict, List, Optional, Union

from core.models.session import SessionState, Message, MessageType
from core.models.protocol import EventBatch
from core.models.base import Event, PlayerSpeakPayload, PlayerBuildPayload, VoxelTypeCreatedPayload, VoxelTypeUpdatedPayload, AgentContinuePlanPayload, AgentPerceptionPayload
from core.models.protocol import PlanCommandRegistry


class SessionDataConverter:
    """简化的Unity原始数据到SessionState转换器"""
    
    @staticmethod
    def format_image_placeholder(images: Optional[List]) -> str:
        """将图片列表转换为占位符字符串
        
        Args:
            images: 图片列表，可能是Image对象列表或None
            
        Returns:
            占位符字符串，如 "Image" 或 "3 Images"
        """
        if not images:
            return ""
        
        count = len(images)
        if count == 1:
            return "Image"
        else:
            return f"{count} Images"
    
    @staticmethod
    def should_include_event(event: Event) -> bool:
        """判断是否应该包含此事件到对话历史
        
        Args:
            event: 事件对象
            
        Returns:
            True if should include, False otherwise
        """
        # 过滤掉player_speak事件，因为这些已经是用户的chat消息
        if event.type == "player_speak":
            return False
        
        # 只保留有意义的事件
        meaningful_events = ["player_build", "voxel_type_created", "voxel_type_modified", "agent_continue_plan", "agent_perception"]
        return event.type in meaningful_events
    
    @staticmethod
    def format_event_message(event: Event) -> tuple[str, Optional[Dict]]:
        """格式化事件为消息内容和载荷
        
        Args:
            event: 事件对象
            
        Returns:
            (content, payload) 元组
        """
        if event.type == "player_build":
            if isinstance(event.payload, PlayerBuildPayload):
                pos = event.payload.voxel_instance.position
                content = f"Player placed {event.payload.voxel_instance.voxel_name} at ({pos.x}, {pos.y}, {pos.z})"
                payload = {
                    "voxel_name": event.payload.voxel_instance.voxel_name,
                    "position": [pos.x, pos.y, pos.z]
                }
            else:
                content = "Player placed a block"
                payload = None
        
        elif event.type == "voxel_type_created":
            if isinstance(event.payload, VoxelTypeCreatedPayload):
                content = f"Created voxel type: {event.payload.voxel_type.name}"
                payload = {"voxel_type_name": event.payload.voxel_type.name}
            else:
                content = "Created new voxel type"
                payload = None
        
        elif event.type == "voxel_type_modified":
            if isinstance(event.payload, VoxelTypeUpdatedPayload):
                content = f"Modified voxel type: {event.payload.voxel_id}"
                payload = {"voxel_id": event.payload.voxel_id}
            else:
                content = "Modified voxel type"
                payload = None
        
        elif event.type == "agent_continue_plan":
            if isinstance(event.payload, AgentContinuePlanPayload):
                # 处理图片占位符
                image_placeholder = SessionDataConverter.format_image_placeholder(event.payload.image)
                image_part = f" with {image_placeholder}" if image_placeholder else ""
                
                content = f"Agent continues planning: {event.payload.current_summary}{image_part}"
                payload = {
                    "current_summary": event.payload.current_summary,
                    "possible_next_steps": event.payload.possible_next_steps,
                    "has_images": bool(event.payload.image)
                }
            else:
                content = "Agent continues planning"
                payload = None
        
        elif event.type == "agent_perception":
            if isinstance(event.payload, AgentPerceptionPayload):
                # 处理图片占位符
                image_placeholder = SessionDataConverter.format_image_placeholder(event.payload.image)
                image_part = f" with {image_placeholder}" if image_placeholder else ""
                
                # 处理附近体素信息
                voxel_count = len(event.payload.nearby_voxels) if event.payload.nearby_voxels else 0
                voxel_part = f" and {voxel_count} nearby voxels" if voxel_count > 0 else ""
                
                content = f"Agent perception{image_part}{voxel_part}"
                payload = {
                    "has_images": bool(event.payload.image),
                    "nearby_voxel_count": voxel_count
                }
            else:
                content = "Agent perception"
                payload = None
        
        else:
            content = f"Unknown event: {event.type}"
            payload = None
        
        return content, payload
    
    @staticmethod
    def format_command_message(cmd_data, plan_description: Optional[str] = None) -> str:
        """格式化命令为简洁的消息内容
        
        Args:
            cmd_data: 命令数据 (LastCommand对象或字典)
            plan_description: 对应计划的描述
            
        Returns:
            格式化的命令消息
        """
        # 处理 LastCommand 对象或字典
        if hasattr(cmd_data, 'type'):
            # Pydantic 模型对象
            cmd_type = cmd_data.type
            phase = cmd_data.phase
            params = cmd_data.params
        else:
            # 字典格式
            cmd_type = cmd_data.get("type", "unknown")
            phase = cmd_data.get("phase", "unknown")
            params = cmd_data.get("params", {})
        
        # 使用计划描述，如果没有则使用默认格式
        if plan_description:
            return f"{phase.title()}: {plan_description}"
        
        # 备用格式
        if cmd_type == "create_voxel_type":
            voxel_type = params.get("voxel_type", {}) if isinstance(params, dict) else getattr(params, "voxel_type", {})
            name = voxel_type.get("name", "unknown") if isinstance(voxel_type, dict) else getattr(voxel_type, "name", "unknown")
            return f"{phase.title()}: Create voxel type '{name}'"
        elif cmd_type == "place_block":
            return f"{phase.title()}: Place blocks"
        else:
            return f"{phase.title()}: {cmd_type}"
    
    @classmethod
    def process_event_batch(cls, event_batch: EventBatch, session_state: Optional[SessionState] = None, plan_registry: Optional[PlanCommandRegistry] = None) -> SessionState:
        """简化的EventBatch处理
        
        Args:
            event_batch: Unity发送的事件批次
            session_state: 现有的会话状态，如果为None则创建新的
            
        Returns:
            更新后的SessionState
        """
        if session_state is None:
            session_state = SessionState(
                session_id=event_batch.session_id,
                conversation_history=[]
            )
        
        # 获取世界时间戳
        world_timestamp = "000000"
        if event_batch.game_state:
            world_timestamp = event_batch.game_state.timestamp
        
        # 1. 处理用户聊天事件 (player_speak)
        for event in event_batch.events:
            if event.type == "player_speak":
                if isinstance(event.payload, PlayerSpeakPayload):
                    content = event.payload.text
                    # 处理图片占位符
                    if event.payload.image:
                        content += " [Image]"
                elif isinstance(event.payload, dict):
                    content = event.payload.get("text", "")
                    # 处理字典格式的图片信息
                    if event.payload.get("image"):
                        content += " [Image]"
                else:
                    content = "User message"
                
                session_state.add_message(
                    role="user",
                    content=content,
                    msg_type=MessageType.CHAT,
                    world_timestamp=event.timestamp
                )
        
        # 2. 处理有意义的玩家事件
        for event in event_batch.events:
            if cls.should_include_event(event):
                content, payload = cls.format_event_message(event)
                session_state.add_message(
                    role="player",
                    content=content,
                    msg_type=MessageType.EVENT,
                    world_timestamp=event.timestamp,
                    payload=payload
                )
        
        # 3. 处理AI命令响应
        if event_batch.game_state and event_batch.game_state.last_commands:
            cls._process_commands(event_batch.game_state, session_state, plan_registry)
        
        return session_state
    
    @classmethod
    def _process_commands(cls, game_state, session_state: SessionState, plan_registry: Optional[PlanCommandRegistry] = None) -> None:
        """处理GameState中的last_commands，使用注册表获取Plan信息"""
        
        for cmd_data in game_state.last_commands or []:
            # 处理 LastCommand 对象或字典
            if hasattr(cmd_data, 'id'):
                # Pydantic 模型对象
                command_id = cmd_data.id
                cmd_type = cmd_data.type
                cmd_phase = cmd_data.phase
                cmd_params = cmd_data.params
            else:
                # 字典格式
                command_id = cmd_data.get("id", "unknown")
                cmd_type = cmd_data.get("type")
                cmd_phase = cmd_data.get("phase")
                cmd_params = cmd_data.get("params", {})
            
            # 从Plan-Command注册表获取对应的计划信息
            plan_info = None
            if plan_registry:
                plan_info = plan_registry.get_plan_info_for_command(session_state.session_id, command_id)
            
            # 提取计划信息
            plan_id = plan_info.get("plan_id") if plan_info else None
            plan_description = plan_info.get("plan_description") if plan_info else None
            
            # 格式化命令消息
            content = cls.format_command_message(cmd_data, plan_description)
            
            # 简化的载荷信息 - 使用从注册表获取的plan信息
            payload = {
                "command_type": cmd_type,
                "phase": cmd_phase,
                "plan_id": plan_id,
                "plan_description": plan_description
            }
            
            session_state.add_message(
                role="agent",
                content=content,
                msg_type=MessageType.EVENT,
                world_timestamp=game_state.timestamp,
                payload=payload
            )
