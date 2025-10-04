from typing import Dict, List
import time

class SessionManager:
    def __init__(self, session_timeout: int = 1800):  # 默认30分钟超时
        self.sessions: Dict[str, dict] = {}
        self.session_timeout = session_timeout
    
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """获取会话历史记录，如果会话过期则返回空列表"""
        session = self.sessions.get(session_id)
        if not session:
            return []
            
        # 检查会话是否过期
        if time.time() - session['last_active'] > self.session_timeout:
            self.clear_session(session_id)
            return []
            
        # 更新最后活动时间
        session['last_active'] = time.time()
        return session['history']
    
    def add_message(self, session_id: str, role: str, content: str):
        """添加新消息到会话历史"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'history': [],
                'last_active': time.time()
            }
        
        self.sessions[session_id]['history'].append({
            'role': role,
            'content': content
        })
        self.sessions[session_id]['last_active'] = time.time()
        
        # 保持历史记录在合理范围内
        MAX_HISTORY = 10
        if len(self.sessions[session_id]['history']) > MAX_HISTORY * 2:
            self.sessions[session_id]['history'] = self.sessions[session_id]['history'][-MAX_HISTORY * 2:]
    
    def clear_session(self, session_id: str):
        """清除指定会话的历史记录"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def cleanup_expired_sessions(self):
        """清理所有过期的会话"""
        current_time = time.time()
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if current_time - session['last_active'] > self.session_timeout
        ]
        for session_id in expired_sessions:
            self.clear_session(session_id) 