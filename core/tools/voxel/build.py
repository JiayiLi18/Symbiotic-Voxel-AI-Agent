# core/tools/voxel/build.py
from typing import List, Dict, Tuple, Optional
from core.models.game_state import GameState
from core.tools.database.voxel_db import VoxelDB

class VoxelBuilder:
    def __init__(self, db_path: str):
        self.voxel_db = VoxelDB(db_path)
    
    async def build_structure(
        self,
        structure_type: str,
        start_pos: Tuple[int, int, int],
        dimensions: Tuple[int, int, int],
        voxel_type: str,
        game_state: GameState
    ) -> Dict:
        """建造预定义的结构"""
        if structure_type == "wall":
            return await self._build_wall(start_pos, dimensions, voxel_type, game_state)
        elif structure_type == "floor":
            return await self._build_floor(start_pos, dimensions, voxel_type, game_state)
        elif structure_type == "cube":
            return await self._build_cube(start_pos, dimensions, voxel_type, game_state)
        else:
            raise ValueError(f"Unknown structure type: {structure_type}")
    
    async def _build_wall(
        self,
        start_pos: Tuple[int, int, int],
        dimensions: Tuple[int, int, int],
        voxel_type: str,
        game_state: GameState
    ) -> Dict:
        """建造墙壁"""
        x, y, z = start_pos
        width, height, _ = dimensions
        built_positions = []
        
        # 检查voxel类型是否存在
        voxel_data = self.voxel_db.get_voxel_by_name(voxel_type)
        if not voxel_data:
            raise ValueError(f"Voxel type '{voxel_type}' not found")
            
        # 在指定范围内放置voxel
        for dx in range(width):
            for dy in range(height):
                pos = (x + dx, y + dy, z)
                if self._is_valid_position(pos, game_state):
                    built_positions.append(pos)
                    
        return {
            "structure_type": "wall",
            "voxel_type": voxel_type,
            "positions": built_positions
        }
    
    def _is_valid_position(
        self,
        pos: Tuple[int, int, int],
        game_state: GameState
    ) -> bool:
        """检查位置是否有效"""
        x, y, z = pos
        
        # 检查是否在建造区域内
        if not (game_state.build_area["min"][0] <= x <= game_state.build_area["max"][0] and
                game_state.build_area["min"][1] <= y <= game_state.build_area["max"][1] and
                game_state.build_area["min"][2] <= z <= game_state.build_area["max"][2]):
            return False
            
        # 检查位置是否已被占用
        pos_key = f"{x},{y},{z}"
        return pos_key not in game_state.current_voxels