# core/models/protocol.py
# Unity通信协议模型 - 定义与Unity之间的数据交换格式

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, TYPE_CHECKING, Union, Literal
from datetime import datetime
from core.models.base import (
    Event, Plan, Command, VoxelInstance,
    CreateVoxelTypeParams, UpdateVoxelTypeParams, 
    PlaceBlockParams, DestroyBlockParams,
    MoveToParams, ContinuePlanParams
)

if TYPE_CHECKING:
    from core.models.game_state import GameState

class EventBatch(BaseModel):
    """事件批次模型 - 简化版本，直接使用GameState
    
    主要用途:
    1. 在API层面批量接收和处理事件
    2. 维护事件处理的会话上下文
    
    属性:
        session_id (str): 会话ID，用于关联到特定的游戏会话
        events (List[Event]): 需要处理的事件列表
        game_state (Optional[GameState]): 当前游戏状态（Unity直接发送此格式）
    """
    session_id: str
    events: List[Event]
    game_state: Optional['GameState'] = None  # Unity直接发送GameState格式

class PlanPermission(BaseModel):
    """Unity返回的计划许可模型
    
    当玩家同意某些计划后，Unity发送此数据结构
    包含同意的计划列表和拒绝的计划及改进理由/补充信息
    补充信息帮助AI理解玩家的需求和意图，或者根据改进建议使用continue_plan重新/继续计划
    使用统一ID格式
    """
    session_id: str = Field(..., description="Session ID in format: sess_<timestamp>_<random>")
    goal_id: str = Field(..., description="Goal ID in format: goal_<session_suffix>_<sequence>")
    goal_label: str = Field(..., description="Human-readable goal description")
    approved_plans: List[Plan] = Field(..., description="玩家批准的计划列表")
    additional_info: Optional[str] = Field(None, description="玩家返回的补充信息/改进理由")
    game_state: Optional['GameState'] = Field(None, description="当前游戏状态")

class PlanCommandMapping(BaseModel):
    """Plan-Command映射关系
    
    存储计划和命令之间的对应关系
    """
    session_id: str
    goal_id: str
    mappings: Dict[str, Dict] = Field(default_factory=dict, description="command_id -> plan_info 的映射")
    
    def add_mapping(self, command_id: str, plan_id: int, plan_description: str, plan_action_type: str):
        """添加命令到计划的映射"""
        self.mappings[command_id] = {
            "plan_id": plan_id,
            "plan_description": plan_description,
            "plan_action_type": plan_action_type
        }
    
    def get_plan_info(self, command_id: str) -> Optional[Dict]:
        """根据命令ID获取对应的计划信息"""
        return self.mappings.get(command_id)

class PlanCommandRegistry:
    """Plan-Command注册表
    
    管理所有会话的Plan-Command映射关系
    """
    
    def __init__(self):
        self.mappings: Dict[str, PlanCommandMapping] = {}  # session_id -> mapping
        self._approved_plans: Dict[str, List[Plan]] = {}  # session_id -> approved_plans
    
    def register_plan_permission(self, permission: PlanPermission) -> PlanCommandMapping:
        """注册计划许可，创建Plan-Command映射准备
        
        Args:
            permission: Unity返回的计划许可
            
        Returns:
            创建的映射对象，等待Command填充
        """
        mapping = PlanCommandMapping(
            session_id=permission.session_id,
            goal_id=permission.goal_id
        )
        
        # 存储批准的计划信息，供后续映射使用
        self._approved_plans[permission.session_id] = permission.approved_plans
        
        self.mappings[permission.session_id] = mapping
        return mapping
    
    def map_command_to_plan(self, session_id: str, command_id: str, plan_id: int) -> bool:
        """将命令映射到计划
        
        Args:
            session_id: 会话ID
            command_id: 命令ID
            plan_id: 计划ID
        """
        if session_id not in self.mappings or session_id not in self._approved_plans:
            return False
        
        mapping = self.mappings[session_id]
        approved_plans = self._approved_plans[session_id]
        
        # 从已批准的计划中找到对应的plan信息
        for plan in approved_plans:
            if plan.id == plan_id:
                mapping.add_mapping(
                    command_id=command_id,
                    plan_id=plan_id,
                    plan_description=plan.description,
                    plan_action_type=plan.action_type
                )
                return True
        
        return False
    
    def get_plan_info_for_command(self, session_id: str, command_id: str) -> Optional[Dict]:
        """根据会话ID和命令ID获取计划信息"""
        if session_id not in self.mappings:
            return None
        
        return self.mappings[session_id].get_plan_info(command_id)
    
    def clear_session_mappings(self, session_id: str):
        """清除会话的映射关系"""
        if session_id in self.mappings:
            del self.mappings[session_id]

class CommandBatch(BaseModel):
    """命令批次模型，用于批量发送多个命令
    
    主要用途:
    1. 批量将多个相关命令发送给Unity
    2. 保持命令执行的会话一致性
    
    属性:
        session_id (str): 会话ID，与EventBatch中的session_id对应
        goal_id (str): 目标ID，与PlannerResponse中的goal_id对应
        commands (List[Command]): 需要执行的命令列表
    """
    session_id: str
    goal_id: str = Field(..., description="Goal ID in format: goal_<session_suffix>_<sequence>")
    commands: List[Command]

class SimplePlannerResponse(BaseModel):
    """Simplified response from LLM using simple numeric IDs, converted to full format by Python"""
    goal_label: str = Field(..., description="Human-readable goal description")
    talk_to_player: str = Field(..., description="Immediate response to show to player")
    plan: List[Plan] = Field(default=[], description="Steps with simple numeric IDs (1, 2, 3...)")

class PlannerResponse(BaseModel):
    """Planner的完整响应 - 包含立即对话和后续计划
    
    统一ID格式架构：
    1. goal_id: 整体目标的唯一标识符，格式: goal_<session_suffix>_<sequence>
    2. goal_label: 整体目标的描述性标签（用户可读）
    3. talk_to_player: 立即返回给玩家的对话内容（展示计划，获得许可）
    4. plan: 后续要执行的具体步骤（可能为空，纯聊天时）
    
    流程：
    - 用户说话 → Planner生成 {talk_content + plan}
    - talk_content立即显示给玩家
    - 如果玩家同意 → 执行plan中的步骤
    - 如果玩家不同意 → 重新规划
    """
    session_id: str
    goal_id: str = Field(..., description="Goal ID in format: goal_<session_suffix>_<sequence>")
    goal_label: str = Field(..., description="Human-readable goal description")
    talk_to_player: str = Field(default="Let me help you with that.", description="Immediate response to show to player")
    plan: List[Plan] = Field(default=[], description="Subsequent steps to execute (can be empty for pure chat)")

class SimpleCommand(BaseModel):
    """简化的命令模型，用于LLM输出，不包含ID字段
    
    主要用途:
    1. LLM输出的简化命令格式
    2. 由Python自动生成ID并转换为完整Command
    
    属性:
        type (str): 命令类型
        params: 命令的具体参数
    """
    type: Literal["create_voxel_type", "update_voxel_type", "place_block", "destroy_block", "move_to", "continue_plan"]
    params: Union[
        CreateVoxelTypeParams,
        UpdateVoxelTypeParams, 
        PlaceBlockParams,
        DestroyBlockParams,
        MoveToParams,
        ContinuePlanParams,
        Dict[str, Any]  # 保持向后兼容性
    ]

class SimpleExecutorResponse(BaseModel):
    """Executor的简化响应模型 - 包含生成的命令列表
    
    主要用途:
    1. LLM输出的简化格式，不包含ID
    2. 由Python自动生成ID并转换为完整CommandBatch
    
    属性:
        commands (List[SimpleCommand]): 需要执行的简化命令列表
    """
    commands: List[SimpleCommand] = Field(..., description="Commands to execute")

class PlannerTestResponse(BaseModel):
    """Planner测试响应模型，包含对话和计划以及调试信息
    
    主要用途:
    1. 用于/planner/test端点的响应
    2. 包含生成的对话内容、计划和调试信息
    
    属性:
        session_id (str): 会话ID
        response (PlannerResponse): 生成的完整响应（对话+计划）
        debug_info (Optional[Dict]): 调试信息，包含system_prompt等
    """
    response: PlannerResponse
    debug_info: Optional[Dict[str, Any]] = None

# 解决 Pydantic 循环引用问题
def rebuild_models():
    """重建模型以解决循环引用"""
    try:
        from core.models.game_state import GameState
        EventBatch.model_rebuild()
        PlanPermission.model_rebuild()
    except ImportError:
        pass  # 如果 GameState 还未定义，跳过

# 调用重建
rebuild_models()