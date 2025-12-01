# core/tools/session/manager.py
from typing import Dict, List, Optional

from core.models.session import SessionState, MessageType
from core.models.protocol import EventBatch
from core.models.protocol import PlanPermission, PlanCommandRegistry
from core.tools.id_generator import new_session_id
from .converter import SessionDataConverter

MAX_HISTORY = 15 # 会话历史记录最大长度

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}
        self.converter = SessionDataConverter()
        self.plan_registry = PlanCommandRegistry()  # Plan-Command映射注册表
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        """获取会话状态"""
        return self.sessions.get(session_id)
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> SessionState:
        """获取或创建会话状态"""
        if not session_id:  # 处理 None 或空字符串
            session_id = new_session_id()
        
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(
                session_id=session_id,
                conversation_history=[],
                goal_sequence=0
            )
        
        return self.sessions[session_id]
    
    def get_next_goal_sequence(self, session_id: str) -> int:
        """获取并递增goal序列号
        
        Args:
            session_id: 会话ID
            
        Returns:
            int: 下一个goal序列号（从1开始）
        """
        session = self.get_or_create_session(session_id)
        session.goal_sequence += 1
        return session.goal_sequence
    
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """获取会话历史记录，包含消息类型信息"""
        session = self.get_session(session_id)
        if not session:
            return []
        
        # 转换为包含类型信息的格式
        return [
            {
                'role': msg.role,
                'content': msg.content,
                'type': msg.type.value  # 添加消息类型信息 (chat/event)
            }
            for msg in session.get_recent_messages(MAX_HISTORY)
        ]
    
    def process_event_batch(self, event_batch: EventBatch) -> SessionState:
        """处理Unity发送的事件批次，更新会话状态
        
        Args:
            event_batch: Unity发送的事件批次
            
        Returns:
            更新后的SessionState
        """
        session_id = event_batch.session_id
        existing_session = self.get_session(session_id)
        
        # 使用转换器处理事件批次，传入Plan注册表
        updated_session = self.converter.process_event_batch(event_batch, existing_session, self.plan_registry)
        
        # 保存更新后的会话
        self.sessions[session_id] = updated_session
        
        # 保持历史记录在合理范围内
        self._trim_session_history(updated_session)
        
        return updated_session
    
    def process_plan_permission(self, permission: PlanPermission) -> None:
        """处理Unity返回的计划许可
        
        这是Plan-Command映射的关键步骤：
        1. 注册批准的计划
        2. 为后续的Command创建映射准备
        
        Args:
            permission: Unity返回的计划许可
        """
        # 注册计划许可到映射注册表
        mapping = self.plan_registry.register_plan_permission(permission)
        
        # 存储批准的计划信息，供后续Command映射使用
        for plan in permission.approved_plans:
            # 这里可以预先生成command_id，或者等待Unity发送Command时再映射
            # 具体实现取决于你们的Command ID生成策略
            pass
        
        print(f"✅ Registered plan permission for session {permission.session_id}")
        print(f"   Goal: {permission.goal_label}")
        print(f"   Approved plans: {len(permission.approved_plans)}")
    
    def map_command_to_plan(self, session_id: str, command_id: str, plan_id: int) -> bool:
        """将命令映射到计划
        
        当生成Command时调用此方法建立映射关系
        
        Args:
            session_id: 会话ID
            command_id: 命令ID  
            plan_id: 计划ID
            
        Returns:
            映射是否成功
        """
        return self.plan_registry.map_command_to_plan(session_id, command_id, plan_id)
    
    def add_message(self, session_id: str, role: str, content: str, msg_type: MessageType = MessageType.CHAT, world_timestamp: str = "000000"):
        """添加新消息到会话历史（向后兼容）"""
        session = self.get_session(session_id)
        if session is None:
            session = SessionState(
                session_id=session_id,
                conversation_history=[],
                goal_sequence=0
            )
            self.sessions[session_id] = session
        
        session.add_message(role=role, content=content, msg_type=msg_type, world_timestamp=world_timestamp)
        self._trim_session_history(session)
    
    def clear_session(self, session_id: str):
        """清除指定会话的历史记录"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    
    def _trim_session_history(self, session: SessionState):
        """保持会话历史在合理范围内"""
        if len(session.conversation_history) > MAX_HISTORY * 2:
            session.conversation_history = session.conversation_history[-MAX_HISTORY * 2:]

