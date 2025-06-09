# core/tools/session/manager.py
from typing import Dict, List, Optional
from datetime import datetime
import time
from core.models.session import SessionState, ImportantInfo
from core.models.game_state import GameState

class SessionManager:
    def __init__(self, session_timeout: int = 1800):  # 默认30分钟超时
        self.sessions: Dict[str, SessionState] = {}
        self.session_timeout = session_timeout
        self.MAX_HISTORY = 10  # 每个角色保留的最大消息数

    def get_or_create_session(self, session_id: str) -> SessionState:
        """获取或创建会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(
                session_id=session_id,
                conversation_history=[],
                important_info=[],
                current_theme=None,
                last_active=time.time(),
                game_state=GameState()  # 初始化游戏状态
            )
        elif self._is_session_expired(session_id):
            # 如果会话过期，保留重要信息但清除历史记录
            self.sessions[session_id].conversation_history = []
            self.sessions[session_id].last_active = time.time()
            
        return self.sessions[session_id]

    def add_message(self, 
                   session_id: str, 
                   role: str, 
                   content: str,
                   analyze_importance: bool = True) -> Optional[ImportantInfo]:
        """
        添加新消息到会话历史
        Args:
            session_id: 会话ID
            role: 消息角色 ('user' 或 'assistant')
            content: 消息内容
            analyze_importance: 是否分析消息重要性
        Returns:
            Optional[ImportantInfo]: 如果发现重要信息则返回
        """
        session = self.get_or_create_session(session_id)
        
        # 添加消息到历史记录
        session.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        # 保持历史记录在合理范围内
        if len(session.conversation_history) > self.MAX_HISTORY * 2:
            # 保留每个角色最近的消息
            user_messages = [msg for msg in session.conversation_history if msg['role'] == 'user'][-self.MAX_HISTORY:]
            assistant_messages = [msg for msg in session.conversation_history if msg['role'] == 'assistant'][-self.MAX_HISTORY:]
            session.conversation_history = sorted(
                user_messages + assistant_messages,
                key=lambda x: x['timestamp']
            )

        # 分析消息重要性
        important_info = None
        if analyze_importance and role == 'user':
            important_info = self._analyze_message_importance(session, content)
            if important_info:
                session.important_info.append(important_info)

        # 更新最后活动时间
        session.last_active = time.time()
        
        return important_info

    def get_conversation_history(self, 
                               session_id: str, 
                               limit: int = None) -> List[Dict]:
        """获取会话历史记录"""
        session = self.get_or_create_session(session_id)
        history = session.conversation_history
        if limit:
            history = history[-limit:]
        return history

    def get_important_info(self, 
                          session_id: str,
                          category: str = None) -> List[ImportantInfo]:
        """获取重要信息"""
        session = self.get_or_create_session(session_id)
        if category:
            return [info for info in session.important_info if info.category == category]
        return session.important_info

    def update_game_state(self, 
                         session_id: str, 
                         game_state: GameState) -> None:
        """更新游戏状态"""
        session = self.get_or_create_session(session_id)
        session.game_state = game_state

    def clear_session(self, session_id: str, keep_important_info: bool = True) -> None:
        """
        清除会话
        Args:
            session_id: 会话ID
            keep_important_info: 是否保留重要信息
        """
        if session_id in self.sessions:
            if keep_important_info:
                important_info = self.sessions[session_id].important_info
                self.sessions[session_id] = SessionState(
                    session_id=session_id,
                    conversation_history=[],
                    important_info=important_info,
                    current_theme=None,
                    last_active=time.time(),
                    game_state=GameState()
                )
            else:
                del self.sessions[session_id]

    def _is_session_expired(self, session_id: str) -> bool:
        """检查会话是否过期"""
        if session_id not in self.sessions:
            return True
        return time.time() - self.sessions[session_id].last_active > self.session_timeout

    def _analyze_message_importance(self, 
                                  session: SessionState, 
                                  message: str) -> Optional[ImportantInfo]:
        """
        分析消息的重要性
        返回ImportantInfo或None
        """
        # 构建分析提示词
        analysis_prompt = f"""
        Analyze this message for important information:
        Message: {message}
        
        Current context:
        - Theme: {session.current_theme or 'Not set'}
        - Known preferences: {[info.content for info in session.important_info if info.category == 'preference']}
        
        Extract any important information about:
        1. Player preferences
        2. Building themes
        3. Project goals
        4. Special requests
        """
        
        # TODO: 调用AI分析消息
        # 这里需要实现实际的AI调用逻辑
        # 暂时返回None
        return None