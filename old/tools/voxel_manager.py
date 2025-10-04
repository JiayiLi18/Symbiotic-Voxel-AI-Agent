import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Union, Tuple
from pydantic import BaseModel

class VoxelTypeParams(BaseModel):
    """体素类型创建参数模型"""
    name: str
    description: str = ""
    texture: str = ""
    is_transparent: bool = False
    # Note: base_color is always [255, 255, 255] in Python, actual color is handled by Unity

class VoxelManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._cache: Optional[Dict] = None
        self._last_read_time = 0
    
    def _should_reload(self) -> bool:
        """检查是否需要重新加载数据库"""
        if not self._cache or not self._last_read_time:
            return True
        
        try:
            mtime = os.path.getmtime(self.db_path)
            return mtime > self._last_read_time
        except OSError:
            return True
    
    def load_db(self) -> List[Dict]:
        """加载或重新加载数据库，返回voxel列表"""
        try:
            if self._should_reload():
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._cache = data
                self._last_read_time = os.path.getmtime(self.db_path)
            return self._cache.get('voxels', [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load voxel database: {e}")
            return []

    def save_db(self, voxels: List[Dict]) -> None:
        """保存voxel数据库"""
        try:
            data = {
                "revision": datetime.utcnow().isoformat("T") + "Z",
                "voxels": voxels
            }
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self._cache = data
            self._last_read_time = os.path.getmtime(self.db_path)
        except Exception as e:
            raise Exception(f"Failed to save voxel database: {e}")

    def get_voxel_by_id(self, voxel_id: int) -> Optional[Dict]:
        """通过ID获取voxel"""
        voxels = self.load_db()
        for voxel in voxels:
            if voxel.get('id') == voxel_id:
                return voxel
        return None

    def get_voxel_by_name(self, name: str) -> Optional[Dict]:
        """通过名称获取voxel"""
        voxels = self.load_db()
        for voxel in voxels:
            if voxel.get('name').lower() == name.lower():
                return voxel
        return None

    def _get_next_voxel_id(self) -> int:
        """获取下一个可用的voxel ID"""
        voxels = self.load_db()
        max_id = -1
        for voxel in voxels:
            if "id" in voxel and voxel["id"] > max_id:
                max_id = voxel["id"]
        return max_id + 1

    def create_voxel_type(self, params: VoxelTypeParams) -> Dict:
        """创建新的voxel类型"""
        voxels = self.load_db()
        voxel_id = self._get_next_voxel_id()
        
        # 创建新的voxel条目
        new_voxel = {
            "id": voxel_id,
            "name": params.name,
            "texture": params.texture,
            "face_textures": ["", "", "", "", "", ""],
            "base_color": [255, 255, 255],  # 固定使用纯白色，实际颜色由Unity端处理
            "description": params.description,
            "is_transparent": params.is_transparent
        }
        
        voxels.append(new_voxel)
        self.save_db(voxels)
        
        return new_voxel

    def update_voxel_type(self, voxel_id: int, params: Dict) -> Optional[Dict]:
        """更新现有的voxel类型
        
        Args:
            voxel_id: 要更新的voxel的ID
            params: 要更新的参数字典，可包含：
                   - name: 新的名称
                   - texture: 新的贴图
                   - description: 新的描述
                   - is_transparent: 是否透明
                   注意：base_color始终为[255, 255, 255]，实际颜色由Unity端处理
        """
        voxels = self.load_db()
        for i, voxel in enumerate(voxels):
            if voxel.get('id') == voxel_id:
                # 更新提供的字段
                if 'name' in params:
                    voxel['name'] = params['name']
                if 'texture' in params:
                    voxel['texture'] = params['texture']
                if 'description' in params:
                    voxel['description'] = params['description']
                if 'is_transparent' in params:
                    voxel['is_transparent'] = params['is_transparent']
                
                self.save_db(voxels)
                return voxel
        
        return None

    def delete_voxel_type(self, voxel_id: int) -> bool:
        """删除指定的voxel类型"""
        voxels = self.load_db()
        for i, voxel in enumerate(voxels):
            if voxel.get('id') == voxel_id:
                voxels.pop(i)
                self.save_db(voxels)
                return True
        return False

    def get_voxel_summary(self, detailed: bool = False) -> str:
        """生成当前voxel数据库的摘要信息"""
        voxels = self.load_db()
        if not voxels:
            return "No voxels defined yet."
        
        categories: Dict[str, List] = {
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
            elif any(word in name or word in desc for word in ['dirt', 'grass', 'stone', 'granite']):
                category = "Natural"
            elif any(word in name or word in desc for word in ['diamond', 'lapis', 'mineral']):
                category = "Mineral"
            elif voxel.get('is_transparent', False):
                category = "Special"
            else:
                category = "Other"
                
            categories[category].append({
                'id': voxel.get('id'),
                'name': voxel.get('name', 'Unnamed'),
                'description': voxel.get('description', '')
            })
        
        if not detailed:
            summary = ["Current voxels in the game:"]
            for category, category_voxels in categories.items():
                if category_voxels:
                    voxel_names = [v['name'] for v in category_voxels]
                    summary.append(f"\n{category}: {', '.join(voxel_names)}")
            return "\n".join(summary)
        
        summary = ["## Current Voxel Types\n"]
        for category, category_voxels in categories.items():
            if category_voxels:
                summary.append(f"\n### {category}")
                for voxel in category_voxels:
                    summary.append(
                        f"\n- {voxel['name']} (ID: {voxel['id']})"
                        f"\n  Description: {voxel['description'][:100]}..."
                    )
        
        return "\n".join(summary)

    def get_style_analysis(self) -> str:
        """分析现有voxel的风格特点"""
        voxels = self.load_db()
        if not voxels:
            return "No existing voxels to analyze."
        
        names = [voxel.get('name', '') for voxel in voxels]
        
        texture_stats = {
            'with_texture': len([v for v in voxels if v.get('texture')]),
            'with_face_textures': len([v for v in voxels 
                if any(v.get('face_textures', []))]),
            'total': len(voxels)
        }
        
        analysis = [
            "## Style Analysis",
            f"\nTotal voxel types: {len(voxels)}",
            "\nNaming patterns: " + (
                "Consistent" if len(set(len(name.split()) for name in names)) <= 2
                else "Varied"
            ),
            "\nTexture usage:",
            f"- {texture_stats['with_texture']} voxels have main texture",
            f"- {texture_stats['with_face_textures']} voxels use face-specific textures",
            "\nTransparency:",
            f"- {len([v for v in voxels if v.get('is_transparent')])} transparent voxels",
            f"- {len([v for v in voxels if not v.get('is_transparent')])} solid voxels"
        ]
        
        return "\n".join(analysis) 