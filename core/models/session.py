# core/models/session.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union, Tuple, Literal
from datetime import datetime
from enum import Enum
import time

class MessageType(Enum):
    CHAT = "chat"
    EVENT = "event"

class Message(BaseModel):
    """会话消息数据模型"""
    type: MessageType
    role: str  # 'user' 或 'agent'
    content: str
    timestamp: str  # 游戏世界时间 hhmmss格式
    payload: Optional[Dict] = None  # 额外信息载荷

class SessionState(BaseModel):
    """简化的会话状态数据模型 - 只保留核心对话历史"""
    session_id: str
    conversation_history: List[Message]


    def add_message(self, 
                   role: str, 
                   content: str, 
                   msg_type: MessageType = MessageType.CHAT,
                   world_timestamp: str = "000000",
                   payload: Optional[Dict] = None) -> None:
        """添加新消息"""
        self.conversation_history.append(
            Message(
                type=msg_type,
                role=role,
                content=content,
                timestamp=world_timestamp,
                payload=payload
            )
        )



    def get_recent_messages(self, 
                          limit: int = 10, 
                          msg_type: Optional[MessageType] = None) -> List[Message]:
        """获取最近的消息，可以按类型筛选"""
        if msg_type:
            filtered_messages = [msg for msg in self.conversation_history if msg.type == msg_type]
            return filtered_messages[-limit:]
        return self.conversation_history[-limit:]


    class Config:
        """Pydantic配置"""
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            MessageType: lambda v: v.value
        }

class SessionClearRequest(BaseModel):
    """会话清除请求"""
    session_id: str
    clear_all: bool = False  # If True, clears all sessions

class SessionAck(BaseModel):
    """会话操作确认"""
    session_id: str
    status: Literal["cleared", "error"]
    error: str | None = None