import json
from typing import Dict, List, Optional
import os

class VoxelDB:
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
                    self._cache = data.get('voxels', [])
                self._last_read_time = os.path.getmtime(self.db_path)
            return self._cache
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load voxel database: {e}")
            return []
    
    def get_voxel_summary(self, detailed: bool = False) -> str:
        """
        生成当前 voxel 数据库的摘要信息，用于 AI prompt
        Args:
            detailed: 是否返回详细信息，默认False只返回名称列表
        """
        voxels = self.load_db()
        if not voxels:
            return "No voxels defined yet."
        
        # 按类别组织 voxels
        categories: Dict[str, List] = {
            "Basic": [],
            "Natural": [],
            "Mineral": [],
            "Other": []
        }
        
        # 基于名称和描述进行简单分类
        for voxel in voxels:
            name = voxel.get('name', '').lower()
            desc = voxel.get('description', '').lower()
            
            if name in ['air', 'draft']:
                category = "Basic"
            elif any(word in name or word in desc for word in ['dirt', 'grass', 'stone', 'granite']):
                category = "Natural"
            elif any(word in name or word in desc for word in ['diamond', 'lapis', 'mineral']):
                category = "Mineral"
            else:
                category = "Other"
                
            categories[category].append({
                'id': voxel.get('id'),
                'name': voxel.get('name', 'Unnamed'),
                'description': voxel.get('description', '')
            })
        
        # 生成摘要文本
        if not detailed:
            # 简单模式：只列出名称
            summary = ["Current voxels in the game:"]
            for category, category_voxels in categories.items():
                if category_voxels:
                    voxel_names = [v['name'] for v in category_voxels]
                    summary.append(f"\n{category}: {', '.join(voxel_names)}")
            return "\n".join(summary)
        
        # 详细模式
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
    
    def _format_color(self, color_array: List[int]) -> str:
        """将RGB数组转换为十六进制颜色代码"""
        if not isinstance(color_array, list) or len(color_array) < 3:
            return "#FFFFFF"
        return f"#{color_array[0]:02x}{color_array[1]:02x}{color_array[2]:02x}"
    
    def get_style_analysis(self) -> str:
        """
        分析现有 voxel 的风格特点，用于指导新 voxel 的创建
        """
        voxels = self.load_db()
        if not voxels:
            return "No existing voxels to analyze."
        
        # 收集命名模式
        names = [voxel.get('name', '') for voxel in voxels]
        
        # 收集材质使用情况
        texture_stats = {
            'with_texture': len([v for v in voxels if v.get('texture')]),
            'with_face_textures': len([v for v in voxels 
                if any(v.get('face_textures', []))]),
            'total': len(voxels)
        }
        
        # 简单的风格分析
        analysis = [
            "## Style Analysis",
            f"\nTotal voxel types: {len(voxels)}",
            "\nNaming patterns: " + (
                "Consistent" if len(set(len(name.split()) for name in names)) <= 2
                else "Varied"
            ),
            "\nTexture usage:",
            f"- {texture_stats['with_texture']} voxels have main texture",
            f"- {texture_stats['with_face_textures']} voxels use face-specific textures"
        ]
        
        return "\n".join(analysis) 