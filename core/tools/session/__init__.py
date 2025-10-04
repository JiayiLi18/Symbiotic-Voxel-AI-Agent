# core/tools/session/__init__.py
from .manager import SessionManager

class SessionTool:
    """会话工具统一接口 - 完整版"""
    def __init__(self):
        self.manager = SessionManager()
    
    def get_or_create_session(self, session_id: str = None):
        """获取或创建会话状态"""
        return self.manager.get_or_create_session(session_id)
    
    def get_session(self, session_id: str):
        """获取会话状态"""
        return self.manager.get_session(session_id)
    
    def get_history(self, session_id: str):
        """获取会话历史"""
        return self.manager.get_history(session_id)
    
    def add_message(self, session_id: str, role: str, content: str):
        """添加消息"""
        self.manager.add_message(session_id, role, content)
    
    def clear_session(self, session_id: str):
        """清除会话"""
        self.manager.clear_session(session_id)
    
    def clear_all(self):
        """清除所有会话"""
        self.manager.sessions.clear()
    
    def process_event_batch(self, event_batch):
        """处理事件批次"""
        return self.manager.process_event_batch(event_batch)
    
    def process_plan_permission(self, permission):
        """处理计划许可"""
        return self.manager.process_plan_permission(permission)

__all__ = ['SessionTool', 'SessionManager']