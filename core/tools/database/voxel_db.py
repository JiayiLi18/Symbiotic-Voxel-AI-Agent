from typing import Dict, List, Optional
from datetime import datetime
from .base import JSONDatabase
from core.models.base import CreateVoxelTypeParams as VoxelTypeParams
from core.tools.texture.solid_color import ensure_solid_color_texture_from_name
import logging

logger = logging.getLogger(__name__)

class VoxelDatabase(JSONDatabase):
    """Voxel数据库管理 - 支持新的JSON结构（包含next_id和revision）"""
    
    def __init__(self, db_path: str):
        super().__init__(db_path)
        
    def get_all_voxels(self) -> List[Dict]:
        """获取所有voxel"""
        data = self.load()
        return data.get('voxels', [])

    def get_voxel_by_id(self, voxel_id: int) -> Optional[Dict]:
        """通过ID获取voxel"""
        voxels = self.get_all_voxels()
        return next((v for v in voxels if v.get('id') == voxel_id), None)

    def get_voxel_by_name(self, name: str) -> Optional[Dict]:
        """通过名称获取voxel"""
        voxels = self.get_all_voxels()
        return next((v for v in voxels if v.get('name', '').lower() == name.lower()), None)

    def create_voxel(self, params: VoxelTypeParams) -> Dict:
        """创建新的voxel"""
        data = self.load()
        voxels = data.get('voxels', [])
        
        # 使用 next_id 字段来生成新的ID
        next_id = data.get('next_id', 0)
        voxel_id = next_id
        
        voxel_type = params.voxel_type
        new_voxel = {
            "id": voxel_id,
            "name": voxel_type.name,
            "texture": voxel_type.texture,
            "face_textures": voxel_type.face_textures,
            "base_color": [255, 255, 255],  # 默认白色
            "description": voxel_type.description,
            "is_transparent": False  # 默认不透明
        }

        # 如果未提供纹理或提供的是颜色命名纹理，则根据名称生成 16x16 纯色纹理并填充
        try:
            # 处理整体 texture
            if new_voxel.get("texture"):
                try:
                    normalized = ensure_solid_color_texture_from_name(new_voxel["texture"])  # type: ignore
                    new_voxel["texture"] = normalized
                except Exception:
                    pass  # 如果不是颜色命名，保持原样
            # 处理 face_textures
            faces = new_voxel.get("face_textures") or []
            if isinstance(faces, list) and faces:
                normalized_faces = []
                for f in faces[:6]:
                    if f:
                        try:
                            normalized_faces.append(ensure_solid_color_texture_from_name(f))
                        except Exception:
                            normalized_faces.append(f)
                    else:
                        normalized_faces.append("")
                # 补全到6个
                while len(normalized_faces) < 6:
                    normalized_faces.append("")
                new_voxel["face_textures"] = normalized_faces
            else:
                # 如果未提供任何面纹理且未提供整体纹理，则不做处理（保持空），由上层决定
                pass
        except Exception as e:
            logger.warning(f"Failed to ensure solid color texture: {e}")
        
        voxels.append(new_voxel)
        
        # 更新数据库结构
        updated_data = {
            "next_id": next_id + 1,
            "revision": datetime.utcnow().isoformat() + "Z",
            "voxels": voxels
        }
        
        self.save(updated_data)
        logger.info(f"Created voxel '{voxel_type.name}' with ID {voxel_id}")
        return new_voxel

    def update_voxel(self, voxel_id: int, updates: Dict) -> Optional[Dict]:
        """更新voxel"""
        data = self.load()
        voxels = data.get('voxels', [])
        
        for voxel in voxels:
            if voxel.get('id') == voxel_id:
                voxel.update(updates)
                # 如有需要，根据名称生成纯色纹理
                try:
                    if voxel.get("texture"):
                        try:
                            voxel["texture"] = ensure_solid_color_texture_from_name(voxel["texture"])  # type: ignore
                        except Exception:
                            pass
                    faces = voxel.get("face_textures") or []
                    if isinstance(faces, list) and faces:
                        normalized_faces = []
                        for f in faces[:6]:
                            if f:
                                try:
                                    normalized_faces.append(ensure_solid_color_texture_from_name(f))
                                except Exception:
                                    normalized_faces.append(f)
                            else:
                                normalized_faces.append("")
                        while len(normalized_faces) < 6:
                            normalized_faces.append("")
                        voxel["face_textures"] = normalized_faces
                except Exception as e:
                    logger.warning(f"Failed to ensure solid color texture on update: {e}")
                
                # 更新revision时间戳
                updated_data = {
                    "next_id": data.get('next_id', 0),
                    "revision": datetime.utcnow().isoformat() + "Z",
                    "voxels": voxels
                }
                
                self.save(updated_data)
                logger.info(f"Updated voxel with ID {voxel_id}")
                return voxel
        return None

    def delete_voxel(self, voxel_id: int) -> bool:
        """删除voxel"""
        data = self.load()
        voxels = data.get('voxels', [])
        initial_length = len(voxels)
        
        voxels = [v for v in voxels if v.get('id') != voxel_id]
        
        if len(voxels) != initial_length:
            # 更新数据库结构
            updated_data = {
                "next_id": data.get('next_id', 0),
                "revision": datetime.utcnow().isoformat() + "Z",
                "voxels": voxels
            }
            
            self.save(updated_data)
            logger.info(f"Deleted voxel with ID {voxel_id}")
            return True
        return False

    def get_voxel_basic(self) -> List[Dict]:
        """获取所有体素基本信息（id, name, description）"""
        voxels = self.get_all_voxels()
        return [
            {
                'id': voxel.get('id'),
                'name': voxel.get('name'),
                'description': voxel.get('description', '')
            }
            for voxel in voxels
        ]
    
    def get_database_info(self) -> Dict:
        """获取数据库元信息"""
        data = self.load()
        return {
            "next_id": data.get('next_id', 0),
            "revision": data.get('revision', ''),
            "voxel_count": len(data.get('voxels', []))
        }