# core/models/session.py
from pydantic import BaseModel
from typing import List, Dict, Optional, Union, Tuple
from datetime import datetime
from enum import Enum
import time
from .game_state import GameState, VoxelData, ActionType

class MessageType(Enum):
    CHAT = "chat"
    SENSE = "sense"

class Message(BaseModel):
    """会话消息数据模型"""
    type: MessageType
    role: str  # 'user' 或 'assistant' 或 'environment'
    content: str
    timestamp: str  # ISO格式的时间字符串
    related_image: Optional[str] = None
    related_action: Optional[Dict] = None  # 对于SENSE类型的消息，记录相关的动作

class ImportantInfo(BaseModel):
    """重要信息数据模型"""
    timestamp: datetime
    category: str  # 'preference', 'theme', 'goal', 'request', 'environment'
    content: str
    confidence: float  # 0.0 到 1.0
    context: str  # 提取该信息的对话上下文
    source_type: MessageType  # 信息来源类型

    class Config:
        """配置示例"""
        json_schema_extra = {
            "example": {
                "timestamp": "2024-03-15T10:30:00",
                "category": "preference",
                "content": "Player prefers medieval style buildings",
                "confidence": 0.85,
                "context": "I really love medieval style castles...",
                "source_type": MessageType.CHAT
            }
        }

class SessionState(BaseModel):
    """会话状态数据模型"""
    session_id: str
    conversation_history: List[Message]
    important_info: List[ImportantInfo]
    current_theme: Optional[str] = None
    last_active: float  # Unix时间戳
    game_state: GameState

    def add_message(self, 
                   role: str, 
                   content: str, 
                   msg_type: MessageType = MessageType.CHAT,
                   image_path: Optional[str] = None,
                   action: Optional[Dict] = None) -> None:
        """添加新消息"""
        self.conversation_history.append(
            Message(
                type=msg_type,
                role=role,
                content=content,
                timestamp=datetime.now().isoformat(),
                related_image=image_path,
                related_action=action
            )
        )
        self.last_active = time.time()

    def add_important_info(self, info: ImportantInfo) -> None:
        """添加重要信息"""
        self.important_info.append(info)

    def get_recent_messages(self, 
                          limit: int = 10, 
                          msg_type: Optional[MessageType] = None) -> List[Message]:
        """获取最近的消息，可以按类型筛选"""
        if msg_type:
            filtered_messages = [msg for msg in self.conversation_history if msg.type == msg_type]
            return filtered_messages[-limit:]
        return self.conversation_history[-limit:]

    def get_important_info_by_category(self, category: str) -> List[ImportantInfo]:
        """获取特定类别的重要信息"""
        return [info for info in self.important_info if info.category == category]

    def update_theme(self, new_theme: str) -> None:
        """更新当前主题"""
        self.current_theme = new_theme
        self.add_important_info(
            ImportantInfo(
                timestamp=datetime.now(),
                category="theme",
                content=new_theme,
                confidence=1.0,
                context="Theme explicitly set",
                source_type=MessageType.CHAT
            )
        )

    def update_game_state(self,
                         voxels: Dict[str, VoxelData],
                         player_pos: Optional[Tuple[int, int, int]] = None,
                         action: Optional[Dict] = None) -> None:
        """更新游戏状态并记录为sense消息"""
        # 更新游戏状态
        self.game_state.update_state(voxels, player_pos, action)
        
        # 记录环境变化
        if action:
            action_type = action.get('type', 'unknown')
            action_desc = self._generate_action_description(action_type, voxels, player_pos)
            
            self.add_message(
                role="environment",
                content=action_desc,
                msg_type=MessageType.SENSE,
                action=action
            )

    def _generate_action_description(self,
                                   action_type: str,
                                   voxels: Dict[str, VoxelData],
                                   player_pos: Optional[Tuple[int, int, int]] = None) -> str:
        """生成环境变化描述"""
        if action_type == ActionType.BUILD.value:
            return f"Player built {len(voxels)} new voxels"
        elif action_type == ActionType.DESTROY.value:
            return f"Player destroyed {len(voxels)} voxels"
        elif action_type == ActionType.MOVE.value and player_pos:
            return f"Player moved to position {player_pos}"
        elif action_type == ActionType.MODIFY.value:
            return f"Player modified {len(voxels)} voxels"
        return f"Environment changed: {action_type}"

    def is_expired(self, timeout: int) -> bool:
        """检查会话是否过期"""
        return time.time() - self.last_active > timeout

    def get_context_summary(self) -> Dict:
        """获取当前上下文摘要"""
        return {
            "theme": self.current_theme,
            "recent_chat": self.get_recent_messages(limit=5, msg_type=MessageType.CHAT),
            "recent_actions": self.get_recent_messages(limit=3, msg_type=MessageType.SENSE),
            "important_info": self.important_info[-5:],  # 最近5条重要信息
            "surrounding_voxels": self.game_state.get_surrounding_voxels(),
            "last_action": self.game_state.last_action
        }

    class Config:
        """Pydantic配置"""
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            GameState: lambda v: v.dict(),
            MessageType: lambda v: v.value
        }