from pydantic import BaseModel
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum

class ActionType(Enum):
    BUILD = "build"
    DESTROY = "destroy"
    MOVE = "move"
    MODIFY = "modify"

class VoxelData(BaseModel):
    """单个Voxel的数据结构"""
    voxel_id: str
    position: Tuple[int, int, int]
    properties: Dict[str, any] = {}
    texture_path: Optional[str] = None

class GameState(BaseModel):
    """游戏状态数据结构"""
    player_position: Tuple[int, int, int]
    current_voxels: Dict[str, VoxelData]  # key: "x,y,z"
    build_area: Dict[str, List[int]]      # 建造区域边界
    last_action: Optional[Dict] = None
    
    def get_surrounding_voxels(self, radius: int = 5) -> Dict[str, VoxelData]:
        """获取玩家周围的voxel"""
        x, y, z = self.player_position
        nearby_voxels = {}
        
        for pos_str, voxel in self.current_voxels.items():
            vx, vy, vz = voxel.position
            if (abs(vx-x) <= radius and 
                abs(vy-y) <= radius and 
                abs(vz-z) <= radius):
                nearby_voxels[pos_str] = voxel
                
        return nearby_voxels

    def update_state(self, 
                    voxels: Dict[str, VoxelData],
                    player_pos: Optional[Tuple[int, int, int]] = None,
                    action: Optional[Dict] = None):
        """更新游戏状态"""
        self.current_voxels.update(voxels)
        if player_pos:
            self.player_position = player_pos
        if action:
            self.last_action = action