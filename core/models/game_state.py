from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Any
from core.models.base import Plan, Command, Position, VoxelInstance, Direction, DirectionalVoxel

class PendingPlan(Plan):
    """Plan 的扩展：用于Unity侧挂起计划的回传，补充目标归属信息"""
    goal_id: str = Field(..., description="Goal ID in format: goal_<session_suffix>_<sequence>")
    goal_label: str = Field(..., description="Human-readable goal description")

class LastCommand(Command):
    """Command 的扩展：用于Unity侧最近命令的回传，补充目标归属与阶段"""
    goal_id: str = Field(..., description="Goal ID in format: goal_<session_suffix>_<sequence>")
    goal_label: str = Field(..., description="Human-readable goal description")
    plan_id: str = Field(..., description="Plan ID in format: plan_<goal_sequence>_<sequence>")
    plan_label: str = Field(..., description="Human-readable plan description")
    phase: Optional[Literal["succeed", "ongoing", "failed"]] = None

class GameState(BaseModel):
    """游戏状态数据结构
    
    主要功能：
    1. 存储游戏世界的当前状态（时间、位置、方向性体素等）
    2. 提供六个方向上最近体素的简洁表示，优化token使用
    3. 管理挂起的计划和最近的命令
    
    方向性体素表示：
    - Unity以Agent为中心发射6条射线（上下前后左右）
    - 返回每个方向最近击中的体素信息（名称、ID、距离）
    - 如果某方向为空气，则显示该方向的最大探测距离
    """
    timestamp: str = Field(..., description="World time hhmmss, range 000000-995959")
    player_abs_position: Position = Field(default_factory=lambda: Position(x=0, y=0, z=0), description="玩家位置")
    agent_abs_position: Position = Field(default_factory=lambda: Position(x=0, y=0, z=0), description="Agent位置")
    directional_voxels: List[DirectionalVoxel] = Field(default_factory=list, description="六个方向上的最近体素信息")
    pending_plans: List[PendingPlan] = Field(default_factory=list, description="挂起的计划，少于3条")
    last_commands: List[LastCommand] = Field(default_factory=list, description="最近的命令，少于3条")
    
    def update_directional_voxels(self, raycast_results: List[Dict[str, Any]]) -> None:
        """更新方向性体素数据
        
        Args:
            raycast_results: Unity射线检测结果列表，每个元素包含:
                - direction: str (up/down/front/back/left/right)
                - hit: bool (是否击中体素)
                - voxel_name: str (体素名称，如果击中)
                - voxel_id: str (体素ID，如果击中)
                - position: List[int] (体素绝对位置 [x,y,z]，如果击中)
                - distance: int (距离)
        """
        self.directional_voxels.clear()
        
        for result in raycast_results:
            direction = Direction(result["direction"])
            distance = result["distance"]
            
            if result["hit"]:
                # 击中体素
                directional_voxel = DirectionalVoxel(
                    direction=direction,
                    voxel_name=result["voxel_name"],
                    voxel_id=result["voxel_id"],
                    distance=distance
                )
            else:
                # 未击中体素（空气或超出探测范围）
                directional_voxel = DirectionalVoxel(
                    direction=direction,
                    voxel_name=None,
                    voxel_id=None,
                    distance=distance
                )
            
            self.directional_voxels.append(directional_voxel)
    
    def get_directional_voxels_info(self) -> str:
        """获取方向性体素的格式化信息，用于context prompt
        
        Returns:
            格式化的字符串，例如:
            "up: stone (id: 3, distance: 2)
            down: dirt (id: 1, distance: 1)
            front: empty (distance: 10)
            back: wood (id: 5, distance: 3)
            left: empty (distance: 10)
            right: cobblestone (id: 4, distance: 4)"
        """
        if not self.directional_voxels:
            return "No directional voxel data available"
        
        # 按固定顺序排列方向
        direction_order = [Direction.UP, Direction.DOWN, Direction.FRONT, Direction.BACK, Direction.LEFT, Direction.RIGHT]
        
        info_lines = []
        for direction in direction_order:
            # 找到对应方向的体素信息
            directional_voxel = next((dv for dv in self.directional_voxels if dv.direction == direction), None)
            if directional_voxel:
                info_lines.append(directional_voxel.to_description())
            else:
                # 如果没有该方向的数据，显示为未知
                info_lines.append(f"{direction.value}: unknown")
        
        return "\n".join(info_lines)
    
    def get_voxel_in_direction(self, direction: Direction) -> Optional[DirectionalVoxel]:
        """获取指定方向的体素信息"""
        return next((dv for dv in self.directional_voxels if dv.direction == direction), None)