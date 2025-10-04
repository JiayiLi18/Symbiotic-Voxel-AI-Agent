from typing import Dict, List, Optional, Tuple
from core.models.base import CreateVoxelTypeParams, UpdateVoxelTypeParams, VoxelType
from .build import VoxelBuilder
from .modify import VoxelModifier
import logging

logger = logging.getLogger(__name__)

class VoxelManager:
    """体素管理器：统一管理体素的创建、修改和建造"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.builder = VoxelBuilder(db_path)
        self.modifier = VoxelModifier(db_path)
    
    # ---- 建造功能 (从VoxelBuilder) -------------------------------
    # TODO: 实现建造相关功能
    
    # ---- 修改功能 (从VoxelModifier) ----------------------------
    async def create_voxel(self, params: CreateVoxelTypeParams) -> Dict:
        """创建新的voxel类型"""
        return await self.modifier.create_voxel(params)
    
    async def modify_voxel(self, params: UpdateVoxelTypeParams) -> Optional[Dict]:
        """修改现有的voxel"""
        return await self.modifier.modify_voxel(params)
    
    async def get_voxel_by_id(self, voxel_id: int) -> Optional[Dict]:
        """根据ID获取体素"""
        return await self.modifier.get_voxel_by_id(voxel_id)
    
    async def get_voxel_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取体素"""
        return await self.modifier.get_voxel_by_name(name)
    
    async def get_all_voxels(self) -> List[Dict]:
        """获取所有体素"""
        return await self.modifier.get_all_voxels()
    
    async def delete_voxel(self, voxel_id: int) -> bool:
        """删除体素"""
        return await self.modifier.delete_voxel(voxel_id)
    
    # ---- 事件处理器 ------------------------------------------
    async def handle_modify_event(self, event_payload: Dict) -> List[Dict]:
        """处理修改事件"""
        try:
            action = event_payload.get("action")
            
            if action == "create":
                # 创建新体素
                voxel_data = event_payload.get("params", {})
                voxel_type = VoxelType(**voxel_data)
                params = CreateVoxelTypeParams(voxel_type=voxel_type)
                
                voxel = await self.create_voxel(params)
                return [{
                    "id": voxel.get("id"),
                    "type": "create_voxel",
                    "params": voxel
                }]
                
            elif action == "modify":
                # 修改现有体素
                voxel_id = event_payload.get("voxel_id")
                voxel_data = event_payload.get("params", {})
                
                voxel_type = VoxelType(**voxel_data)
                params = UpdateVoxelTypeParams(voxel_id=voxel_id, new_voxel_type=voxel_type)
                
                voxel = await self.modify_voxel(params)
                if voxel:
                    return [{
                        "id": voxel.get("id"),
                        "type": "modify_voxel",
                        "params": voxel
                    }]
                    
            elif action == "delete":
                # 删除体素
                voxel_id = event_payload.get("voxel_id")
                success = await self.delete_voxel(int(voxel_id))
                if success:
                    return [{
                        "id": voxel_id,
                        "type": "delete_voxel",
                        "params": {"success": True}
                    }]
                    
            return []
            
        except Exception as e:
            logger.error(f"Error handling modify event: {e}")
            return [] 