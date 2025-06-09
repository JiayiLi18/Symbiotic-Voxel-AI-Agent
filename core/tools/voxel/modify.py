# core/tools/voxel/modify.py
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel
from core.models.game_state import VoxelData
from core.tools.database.voxel_db import VoxelDB

class VoxelModifier:
    def __init__(self, db_path: str):
        self.voxel_db = VoxelDB(db_path)
    
    async def create_voxel(self, params: VoxelData) -> Dict:
        """创建新的voxel类型"""
        voxels = self.voxel_db.load_db()
        voxel_id = self._get_next_voxel_id(voxels)
        
        new_voxel = {
            "id": voxel_id,
            "position": params.position,
            "properties": params.properties,
            "texture_path": params.texture_path
        }
        
        voxels.append(new_voxel)
        self.voxel_db.save_db(voxels)
        return new_voxel
    
    async def modify_voxel(self, voxel_id: str, new_params: Dict) -> Optional[Dict]:
        """修改现有的voxel"""
        voxels = self.voxel_db.load_db()
        for voxel in voxels:
            if voxel["id"] == voxel_id:
                voxel.update(new_params)
                self.voxel_db.save_db(voxels)
                return voxel
        return None

    def _get_next_voxel_id(self, voxels: List[Dict]) -> str:
        """获取下一个可用的voxel ID"""
        max_id = -1
        for voxel in voxels:
            try:
                current_id = int(voxel["id"])
                if current_id > max_id:
                    max_id = current_id
            except (ValueError, KeyError):
                continue
        return str(max_id + 1)