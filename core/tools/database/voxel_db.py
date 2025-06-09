from typing import Dict, List, Optional
from .base import JSONDatabase
from core.models.voxel import VoxelTypeParams

class VoxelDatabase(JSONDatabase):
    """Voxel数据库管理"""
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
        voxels = self.get_all_voxels()
        voxel_id = max((v.get('id', -1) for v in voxels), default=-1) + 1
        
        new_voxel = {
            "id": voxel_id,
            "name": params.name,
            "texture": params.texture,
            "face_textures": [""] * 6,
            "base_color": [255, 255, 255],
            "description": params.description,
            "is_transparent": params.is_transparent
        }
        
        voxels.append(new_voxel)
        self.save({"voxels": voxels})
        return new_voxel

    def update_voxel(self, voxel_id: int, updates: Dict) -> Optional[Dict]:
        """更新voxel"""
        voxels = self.get_all_voxels()
        for voxel in voxels:
            if voxel.get('id') == voxel_id:
                voxel.update(updates)
                self.save({"voxels": voxels})
                return voxel
        return None

    def delete_voxel(self, voxel_id: int) -> bool:
        """删除voxel"""
        voxels = self.get_all_voxels()
        initial_length = len(voxels)
        voxels = [v for v in voxels if v.get('id') != voxel_id]
        if len(voxels) != initial_length:
            self.save({"voxels": voxels})
            return True
        return False

    def get_summary(self) -> str:
        """获取voxel数据库摘要"""
        voxels = self.get_all_voxels()
        categories = self._categorize_voxels(voxels)
        
        summary = ["## Voxel Database Summary"]
        summary.append(f"\nTotal voxels: {len(voxels)}")
        
        for category, items in categories.items():
            if items:
                summary.append(f"\n### {category} ({len(items)})")
                for voxel in items:
                    summary.append(f"- {voxel['name']}")
        
        return "\n".join(summary)

    def _categorize_voxels(self, voxels: List[Dict]) -> Dict[str, List[Dict]]:
        """将voxel按类别分类"""
        categories = {
            "Basic": [],
            "Natural": [],
            "Mineral": [],
            "Special": [],
            "Other": []
        }
        
        for voxel in voxels:
            name = voxel.get('name', '').lower()
            desc = voxel.get('description', '').lower()
            
            if name in ['air', 'draft']:
                category = "Basic"
            elif any(word in name or word in desc for word in ['dirt', 'grass', 'stone']):
                category = "Natural"
            elif any(word in name or word in desc for word in ['diamond', 'mineral']):
                category = "Mineral"
            elif voxel.get('is_transparent', False):
                category = "Special"
            else:
                category = "Other"
                
            categories[category].append(voxel)
        
        return categories