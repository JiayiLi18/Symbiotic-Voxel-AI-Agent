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
    """Session message data model"""
    type: MessageType
    role: str  # 'user' or 'agent'
    content: str
    timestamp: str  # Game world time hhmmss format
    payload: Optional[Dict] = None  # Additional information payload

class SessionState(BaseModel):
    """Simplified session state data model - only keeps core conversation history"""
    session_id: str
    conversation_history: List[Message]
    goal_sequence: int = Field(default=0, description="Current goal sequence number for this session")


    def add_message(self, 
                   role: str, 
                   content: str, 
                   msg_type: MessageType = MessageType.CHAT,
                   world_timestamp: str = "000000",
                   payload: Optional[Dict] = None) -> None:
        """Add new message"""
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
        """Get recent messages, can filter by type"""
        if msg_type:
            filtered_messages = [msg for msg in self.conversation_history if msg.type == msg_type]
            return filtered_messages[-limit:]
        return self.conversation_history[-limit:]


    class Config:
        """Pydantic configuration"""
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            MessageType: lambda v: v.value
        }

class SessionClearRequest(BaseModel):
    """Session clear request"""
    session_id: str
    clear_all: bool = False  # If True, clears all sessions

class SessionAck(BaseModel):
    """Session operation acknowledgment"""
    session_id: str
    status: Literal["cleared", "error"]
    error: str | None = None