# core/tools/voxel/modify.py
from typing import Dict, List, Optional
from core.models.base import VoxelType, CreateVoxelTypeParams, UpdateVoxelTypeParams
from core.tools.database.voxel_db import VoxelDatabase
import logging

logger = logging.getLogger(__name__)

class VoxelModifier:
    """体素修改器 - 负责创建和修改体素类型"""
    
    def __init__(self, db_path: str):
        self.voxel_db = VoxelDatabase(db_path)
    
    async def create_voxel(self, params: CreateVoxelTypeParams) -> Dict:
        """创建新的voxel类型"""
        try:
            # 使用 VoxelDatabase 的 create_voxel 方法
            new_voxel = self.voxel_db.create_voxel(params)
            logger.info(f"Created new voxel: {new_voxel['name']} (ID: {new_voxel['id']})")
            return new_voxel
        except Exception as e:
            logger.error(f"Failed to create voxel: {str(e)}")
            raise
    
    async def modify_voxel(self, params: UpdateVoxelTypeParams) -> Optional[Dict]:
        """修改现有的voxel：安全合并更新（仅在提供非空值时覆盖）。"""
        try:
            voxel_id = int(params.voxel_id)

            # 读取当前对象以进行安全合并
            current = self.voxel_db.get_voxel_by_id(voxel_id)
            if not current:
                logger.warning(f"Voxel with ID {voxel_id} not found")
                return None

            new_type = params.new_voxel_type

            # 名称与描述：仅在提供非空字符串时覆盖
            updates: Dict = {}
            if getattr(new_type, "name", None):
                updates["name"] = new_type.name
            if getattr(new_type, "description", None):
                # 空字符串视为不更新，避免误清空
                if new_type.description.strip():
                    updates["description"] = new_type.description

            # texture：仅在提供非空时覆盖
            if getattr(new_type, "texture", None):
                if new_type.texture.strip():
                    updates["texture"] = new_type.texture

            # face_textures：逐面合并；若未提供或为空则保留原值
            if isinstance(getattr(new_type, "face_textures", None), list) and new_type.face_textures:
                merged_faces: list = []
                old_faces = current.get("face_textures") or []
                # 填充到 6 项
                while len(old_faces) < 6:
                    old_faces.append("")
                # 合并：新值有内容则覆盖，否则保留旧值
                for i in range(6):
                    new_val = new_type.face_textures[i] if i < len(new_type.face_textures) else ""
                    merged_faces.append(new_val if (isinstance(new_val, str) and new_val.strip()) else old_faces[i])
                updates["face_textures"] = merged_faces

            # 使用 VoxelDatabase 的 update_voxel 方法（会做颜色文件名规范化与生成）
            updated_voxel = self.voxel_db.update_voxel(voxel_id, updates)
            if updated_voxel:
                logger.info(f"Updated voxel: {updated_voxel['name']} (ID: {updated_voxel['id']})")
            else:
                logger.warning(f"Voxel with ID {voxel_id} not found after update")
            return updated_voxel
        except ValueError:
            logger.error(f"Invalid voxel ID format: {params.voxel_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to modify voxel: {str(e)}")
            raise
    
    async def get_voxel_by_id(self, voxel_id: int) -> Optional[Dict]:
        """根据ID获取体素"""
        return self.voxel_db.get_voxel_by_id(voxel_id)
    
    async def get_voxel_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取体素"""
        return self.voxel_db.get_voxel_by_name(name)
    
    async def get_all_voxels(self) -> List[Dict]:
        """获取所有体素"""
        return self.voxel_db.get_all_voxels()
    
    async def delete_voxel(self, voxel_id: int) -> bool:
        """删除体素"""
        try:
            result = self.voxel_db.delete_voxel(voxel_id)
            if result:
                logger.info(f"Deleted voxel with ID: {voxel_id}")
            else:
                logger.warning(f"Voxel with ID {voxel_id} not found for deletion")
            return result
        except Exception as e:
            logger.error(f"Failed to delete voxel: {str(e)}")
            raise