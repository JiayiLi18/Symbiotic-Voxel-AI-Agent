from typing import Dict, List, Optional
from .base import JSONDatabase
from datetime import datetime

class TextureDatabase(JSONDatabase):
    """纹理数据库管理"""
    def __init__(self, db_path: str):
        super().__init__(db_path)
    
    def get_all_textures(self) -> List[Dict]:
        """获取所有纹理"""
        data = self.load()
        return data.get('textures', [])

    def add_texture(self, texture_name: str, texture_path: str, metadata: Dict = None) -> Dict:
        """添加新纹理"""
        textures = self.get_all_textures()
        new_texture = {
            "name": texture_name,
            "path": texture_path,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        textures.append(new_texture)
        self.save({"textures": textures})
        return new_texture

    def get_texture(self, texture_name: str) -> Optional[Dict]:
        """获取纹理信息"""
        textures = self.get_all_textures()
        return next((t for t in textures if t['name'] == texture_name), None)

    def get_summary(self) -> str:
        """获取纹理数据库摘要"""
        textures = self.get_all_textures()
        summary = ["## Texture Database Summary"]
        summary.append(f"\nTotal textures: {len(textures)}")
        
        if textures:
            summary.append("\nRecent textures:")
            for texture in sorted(textures, key=lambda x: x['created_at'], reverse=True)[:5]:
                summary.append(f"- {texture['name']} ({texture['created_at']})")
        
        return "\n".join(summary)