# core/models/protocol.py
# Unity communication protocol models - define data exchange format with Unity

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
    """Event batch model - simplified version, directly uses GameState
    
    Main purposes:
    1. Batch receive and process events at API level
    2. Maintain event processing session context
    
    Attributes:
        session_id (str): Session ID for associating with specific game session
        events (List[Event]): List of events to be processed
        game_state (Optional[GameState]): Current game state (Unity sends this format directly)
    """
    session_id: str
    events: List[Event]
    game_state: Optional['GameState'] = None  # Unity sends GameState format directly

class PlanPermission(BaseModel):
    """Unity returned plan permission model
    
    When player agrees to certain plans, Unity sends this data structure
    Contains approved plan list and rejected plans with improvement reasons/additional information
    Additional information helps AI understand player needs and intentions, or use continue_plan to re/continue planning based on improvement suggestions
    Uses unified ID format
    """
    session_id: str = Field(..., description="Session ID in format: sess_<timestamp>_<random>")
    goal_id: str = Field(..., description="Goal ID in format: goal_<session_suffix>_<sequence>")
    goal_label: str = Field(..., description="Human-readable goal description")
    approved_plans: List[Plan] = Field(..., description="玩家批准的计划列表")
    additional_info: Optional[str] = Field(None, description="玩家返回的补充信息/改进理由")
    game_state: Optional['GameState'] = Field(None, description="当前游戏状态")

class PlanCommandMapping(BaseModel):
    """Plan-Command mapping relationship
    
    Stores correspondence between plans and commands
    """
    session_id: str
    goal_id: str
    mappings: Dict[str, Dict] = Field(default_factory=dict, description="command_id -> plan_info 的映射")
    
    def add_mapping(self, command_id: str, plan_id: int, plan_description: str, plan_action_type: str):
        """Add command to plan mapping"""
        self.mappings[command_id] = {
            "plan_id": plan_id,
            "plan_description": plan_description,
            "plan_action_type": plan_action_type
        }
    
    def get_plan_info(self, command_id: str) -> Optional[Dict]:
        """Get corresponding plan information based on command ID"""
        return self.mappings.get(command_id)

class PlanCommandRegistry:
    """Plan-Command registry
    
    Manages Plan-Command mapping relationships for all sessions
    """
    
    def __init__(self):
        self.mappings: Dict[str, PlanCommandMapping] = {}  # session_id -> mapping
        self._approved_plans: Dict[str, List[Plan]] = {}  # session_id -> approved_plans
    
    def register_plan_permission(self, permission: PlanPermission) -> PlanCommandMapping:
        """Register plan permission, create Plan-Command mapping preparation
        
        Args:
            permission: Plan permission returned by Unity
            
        Returns:
            Created mapping object, waiting for Command population
        """
        mapping = PlanCommandMapping(
            session_id=permission.session_id,
            goal_id=permission.goal_id
        )
        
        # Store approved plan information for subsequent mapping
        self._approved_plans[permission.session_id] = permission.approved_plans
        
        self.mappings[permission.session_id] = mapping
        return mapping
    
    def map_command_to_plan(self, session_id: str, command_id: str, plan_id: int) -> bool:
        """Map command to plan
        
        Args:
            session_id: Session ID
            command_id: Command ID
            plan_id: Plan ID
        """
        if session_id not in self.mappings or session_id not in self._approved_plans:
            return False
        
        mapping = self.mappings[session_id]
        approved_plans = self._approved_plans[session_id]
        
        # Find corresponding plan information from approved plans
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
        """Get plan information based on session ID and command ID"""
        if session_id not in self.mappings:
            return None
        
        return self.mappings[session_id].get_plan_info(command_id)
    
    def clear_session_mappings(self, session_id: str):
        """Clear session mapping relationships"""
        if session_id in self.mappings:
            del self.mappings[session_id]

class CommandBatch(BaseModel):
    """Command batch model for batch sending multiple commands
    
    Main purposes:
    1. Batch send multiple related commands to Unity
    2. Maintain command execution session consistency
    
    Attributes:
        session_id (str): Session ID, corresponds to session_id in EventBatch
        goal_id (str): Goal ID, corresponds to goal_id in PlannerResponse
        commands (List[Command]): List of commands to execute
    """
    session_id: str
    goal_id: str = Field(..., description="Goal ID in format: goal_<session_suffix>_<sequence>")
    commands: List[Command]

class SimplePlannerResponse(BaseModel):
    """Simplified response from LLM using simple numeric IDs, converted to full format by Python"""
    goal_label: str = Field(..., description="One short line describing the goal.")
    talk_to_player: str = Field(..., description="Friendly reply to player, 1-2 short sentences. No technical details.")
    plan: List[Plan] = Field(default=[], description="Array of plan steps. Each step uses simple numeric IDs ('1','2','3'...).")

class PlannerResponse(BaseModel):
    """Planner's complete response - includes immediate dialogue and subsequent plans
    
    Unified ID format architecture:
    1. goal_id: Unique identifier for overall goal, format: goal_<session_suffix>_<sequence>
    2. goal_label: Descriptive label for overall goal (user-readable)
    3. talk_to_player: Immediate dialogue content returned to player (show plans, get permission)
    4. plan: Specific steps to execute subsequently (may be empty for pure chat)
    
    Process:
    - User speaks → Planner generates {talk_content + plan}
    - talk_content immediately shown to player
    - If player agrees → execute steps in plan
    - If player disagrees → replan
    """
    session_id: str
    goal_id: str = Field(..., description="Goal ID in format: goal_<session_suffix>_<sequence>")
    goal_label: str = Field(..., description="One short line describing the goal.")
    talk_to_player: str = Field(default="Let me help you with that.", description="Friendly reply to player, 1-2 short sentences. No technical details.")
    plan: List[Plan] = Field(default=[], description="Subsequent steps to execute (can be empty for pure chat)")

class SimpleCommand(BaseModel):
    """Simplified command model for LLM output, does not include ID field
    
    Main purposes:
    1. Simplified command format output by LLM
    2. Python automatically generates ID and converts to complete Command
    
    Attributes:
        type (str): Command type
        params: Specific parameters for the command
    """
    type: Literal["create_voxel_type", "update_voxel_type", "place_block", "destroy_block", "move_to", "continue_plan"]
    params: Union[
        CreateVoxelTypeParams,
        UpdateVoxelTypeParams, 
        PlaceBlockParams,
        DestroyBlockParams,
        MoveToParams,
        ContinuePlanParams,
        Dict[str, Any]  # Maintain backward compatibility
    ]

class SimpleExecutorResponse(BaseModel):
    """Executor's simplified response model - contains generated command list
    
    Main purposes:
    1. Simplified format output by LLM, does not include ID
    2. Python automatically generates ID and converts to complete CommandBatch
    
    Attributes:
        commands (List[SimpleCommand]): List of simplified commands to execute
    """
    commands: List[SimpleCommand] = Field(..., description="Commands to execute")

class PlannerTestResponse(BaseModel):
    """Planner test response model, includes dialogue and plans as well as debug information
    
    Main purposes:
    1. Response for /planner/test endpoint
    2. Contains generated dialogue content, plans and debug information
    
    Attributes:
        session_id (str): Session ID
        response (PlannerResponse): Generated complete response (dialogue + plans)
        debug_info (Optional[Dict]): Debug information, includes system_prompt etc.
    """
    response: PlannerResponse
    debug_info: Optional[Dict[str, Any]] = None

# Solve Pydantic circular reference issues
def rebuild_models():
    """Rebuild models to solve circular references"""
    try:
        from core.models.game_state import GameState
        EventBatch.model_rebuild()
        PlanPermission.model_rebuild()
    except ImportError:
        pass  # If GameState not yet defined, skip

# Call rebuild
rebuild_models()