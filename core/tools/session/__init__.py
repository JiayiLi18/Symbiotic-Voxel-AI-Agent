# core/tools/session/__init__.py
from .manager import SessionManager
from .analyzer import SessionAnalyzer
from typing import Dict

class SessionTool:
    """会话工具统一接口"""
    def __init__(self, session_timeout: int = 1800):
        self.manager = SessionManager(session_timeout)
        self.analyzer = SessionAnalyzer()
    
    async def process_message(self, 
                            session_id: str, 
                            message: str, 
                            role: str = 'user') -> Dict:
        """处理新消息"""
        # 获取会话
        session = self.manager.get_or_create_session(session_id)
        
        # 添加消息并分析重要信息
        important_info = self.manager.add_message(
            session_id, 
            role, 
            message,
            analyze_importance=True
        )
        
        # 获取相关的历史重要信息
        relevant_info = self.analyzer.get_relevant_info(
            session,
            message
        )
        
        # 如果没有主题，尝试推荐
        if not session.current_theme:
            theme_suggestions = self.analyzer.get_theme_suggestions(session)
        else:
            theme_suggestions = []
        
        return {
            'session_id': session_id,
            'new_important_info': important_info.dict() if important_info else None,
            'relevant_info': [info.dict() for info in relevant_info],
            'theme_suggestions': theme_suggestions,
            'session_summary': self.analyzer.summarize_session(session)
        }

__all__ = ['SessionTool', 'SessionManager', 'SessionAnalyzer']