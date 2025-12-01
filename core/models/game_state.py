from pydantic import BaseModel, Field, model_validator
from typing import Dict, List, Optional, Literal, Any
from core.models.base import Plan, Command, Position, VoxelInstance, Direction, DirectionalVoxel

class PendingPlan(Plan):
    """Extension of Plan: used for Unity side pending plan callback, supplemented with goal ownership information"""
    goal_id: str = Field(..., description="Goal ID in format: goal_<session_suffix>_<sequence>")
    goal_label: str = Field(..., description="Human-readable goal description")

class LastCommand(Command):
    """Extension of Command: used for Unity side recent command callback, supplemented with goal ownership and phase"""
    goal_id: str = Field(..., description="Goal ID in format: goal_<session_suffix>_<sequence>")
    goal_label: str = Field(..., description="Human-readable goal description")
    phase: Optional[Literal["pending", "done", "failed", "cancelled"]] = None

class GameState(BaseModel):
    """Game state data structure
    
    Main functions:
    1. Store current state of the game world (time, position, directional voxels, etc.)
    2. Provide concise representation of nearest voxels in six directions, optimizing token usage
    3. Manage pending plans and recent commands
    4. Store detailed information of nearby voxels for spatial understanding and context analysis
    
    Directional voxel representation:
    - Unity casts 6 rays centered on Agent (up/down/front/back/left/right)
    - Returns nearest hit voxel information in each direction (name, ID, distance)
    - If a direction is air, shows maximum detection distance for that direction
    
    Nearby voxel representation:
    - Stores voxel instances within 5x5x5 range around Agent
    - Used to provide spatial context and estimate quantities
    - Complements directional voxels to provide more complete spatial information
    """
    timestamp: str = Field(..., description="World time hhmmss, range 000000-995959")
    player_abs_position: Position = Field(default_factory=lambda: Position(x=0, y=0, z=0), description="玩家位置")
    agent_abs_position: Position = Field(default_factory=lambda: Position(x=0, y=0, z=0), description="Agent位置")
    directional_voxels: List[DirectionalVoxel] = Field(default_factory=list, description="六个方向上的最近体素信息")
    nearby_voxels: List[VoxelInstance] = Field(default_factory=list, description="附近体素（5x5x5范围）")
    pending_plans: List[PendingPlan] = Field(default_factory=list, description="挂起的计划，少于3条")
    last_commands: List[LastCommand] = Field(default_factory=list, description="最近的命令，少于3条")
    voxel_definitions: List[Dict[str, Any]] = Field(default_factory=list, description="Unity端传来的voxel definitions列表，用于确保id和name的一致性")
    
    @model_validator(mode='before')
    @classmethod
    def transform_unity_format(cls, data: Any) -> Any:
        """Transform Unity data format to expected GameState format"""
        if not isinstance(data, dict):
            return data
        
        result = data.copy()
        
        # 1. Transform position field names and convert float to int
        if "agent_position" in data and "agent_abs_position" not in data:
            agent_pos = data["agent_position"]
            if isinstance(agent_pos, dict):
                result["agent_abs_position"] = {
                    "x": int(float(agent_pos.get("x", 0))),
                    "y": int(float(agent_pos.get("y", 0))),
                    "z": int(float(agent_pos.get("z", 0)))
                }
        
        # 2. Handle player position - Unity sends relative position, we need to convert to absolute
        if "player_position_rel" in data:
            agent_pos = data.get("agent_position", {})
            player_rel = data["player_position_rel"]
            
            # Calculate absolute position and convert float to int
            agent_pos = agent_pos if isinstance(agent_pos, dict) else {"x": 0, "y": 0, "z": 0}
            player_rel = player_rel if isinstance(player_rel, dict) else {"x": 0, "y": 0, "z": 0}
            
            result["player_abs_position"] = {
                "x": int(float(agent_pos.get("x", 0)) + float(player_rel.get("x", 0))),
                "y": int(float(agent_pos.get("y", 0)) + float(player_rel.get("y", 0))),
                "z": int(float(agent_pos.get("z", 0)) + float(player_rel.get("z", 0)))
            }
        
        # 3. Transform six_direction dictionary to directional_voxels list
        if "six_direction" in data and "directional_voxels" not in data:
            six_dir = data["six_direction"]
            directional_voxels = []
            
            direction_mapping = {
                "up": Direction.UP,
                "down": Direction.DOWN,
                "front": Direction.FRONT,
                "back": Direction.BACK,
                "left": Direction.LEFT,
                "right": Direction.RIGHT
            }
            
            for dir_name, dir_data in six_dir.items():
                if isinstance(dir_data, dict):
                    voxel_name = dir_data.get("name")
                    voxel_id = dir_data.get("id")
                    distance = dir_data.get("distance", 10)
                    
                    # If name is "empty" or id is "0", treat as empty
                    if voxel_name == "empty" or voxel_id == "0":
                        voxel_name = None
                        voxel_id = None
                    
                    directional_voxel = {
                        "direction": direction_mapping.get(dir_name, dir_name),
                        "voxel_name": voxel_name,
                        "voxel_id": voxel_id,
                        "distance": int(float(distance))
                    }
                    directional_voxels.append(directional_voxel)
            
            result["directional_voxels"] = directional_voxels
        
        return result
    
    def update_directional_voxels(self, raycast_results: List[Dict[str, Any]]) -> None:
        """Update directional voxel data
        
        Args:
            raycast_results: Unity raycast detection result list, each element contains:
                - direction: str (up/down/front/back/left/right)
                - hit: bool (whether hit voxel)
                - voxel_name: str (voxel name if hit)
                - voxel_id: str (voxel ID if hit)
                - position: List[int] (voxel absolute position [x,y,z] if hit)
                - distance: int (distance)
        """
        self.directional_voxels.clear()
        
        for result in raycast_results:
            direction = Direction(result["direction"])
            distance = result["distance"]
            
            if result["hit"]:
                # Hit voxel
                directional_voxel = DirectionalVoxel(
                    direction=direction,
                    voxel_name=result["voxel_name"],
                    voxel_id=result["voxel_id"],
                    distance=distance
                )
            else:
                # No voxel hit (air or beyond detection range)
                directional_voxel = DirectionalVoxel(
                    direction=direction,
                    voxel_name=None,
                    voxel_id=None,
                    distance=distance
                )
            
            self.directional_voxels.append(directional_voxel)
    
    def update_nearby_voxels(self, nearby_voxels: List[VoxelInstance]) -> None:
        """Update nearby voxel data
        
        Args:
            nearby_voxels: List of voxel instances within 5x5x5 range around Agent
        """
        self.nearby_voxels = nearby_voxels
    
    def get_nearby_voxels_info(self) -> str:
        """Get formatted information of nearby voxels for context prompt
        
        Returns:
            Formatted string, e.g.: "nearby voxels: Dirt*3, Leaves*2, Stone*1"
        """
        if not self.nearby_voxels:
            return "none"
        
        # Count the number of each voxel type
        voxel_counts = {}
        for voxel in self.nearby_voxels:
            voxel_name = voxel.voxel_name
            voxel_counts[voxel_name] = voxel_counts.get(voxel_name, 0) + 1
        
        # Format as "name1*count1, name2*count2" format
        stats_parts = []
        for name, count in sorted(voxel_counts.items()):
            stats_parts.append(f"{name}*{count}")
        
        return f"{', '.join(stats_parts)}"
    
    def get_directional_voxels_info(self) -> str:
        """Get formatted information of directional voxels for context prompt
        
        Returns:
            Formatted string, e.g.:
            "up: stone (id: 3, distance: 2)
            down: dirt (id: 1, distance: 1)
            front: empty (distance: 10)
            back: wood (id: 5, distance: 3)
            left: empty (distance: 10)
            right: cobblestone (id: 4, distance: 4)"
        """
        if not self.directional_voxels:
            return "No directional voxel data available"
        
        # Arrange directions in fixed order
        direction_order = [Direction.UP, Direction.DOWN, Direction.FRONT, Direction.BACK, Direction.LEFT, Direction.RIGHT]
        
        info_lines = []
        for direction in direction_order:
            # Find voxel information for corresponding direction
            directional_voxel = next((dv for dv in self.directional_voxels if dv.direction == direction), None)
            if directional_voxel:
                info_lines.append(directional_voxel.to_description())
            else:
                # If no data for this direction, show as unknown
                info_lines.append(f"{direction.value}: unknown")
        
        return "\n".join(info_lines)
    
    def get_voxel_in_direction(self, direction: Direction) -> Optional[DirectionalVoxel]:
        """Get voxel information in specified direction"""
        return next((dv for dv in self.directional_voxels if dv.direction == direction), None)