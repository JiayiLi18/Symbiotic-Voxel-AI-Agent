from .voxel_db import VoxelDatabase
from .texture_db import TextureDatabase

class DatabaseManager:
    """数据库管理器"""
    def __init__(self, voxel_db_path: str, texture_db_path: str):
        self.voxel_db = VoxelDatabase(voxel_db_path)
        self.texture_db = TextureDatabase(texture_db_path)
    
    def get_database_summary(self) -> str:
        """获取所有数据库的摘要"""
        return "\n\n".join([
            self.voxel_db.get_summary(),
            self.texture_db.get_summary()
        ])

__all__ = ['DatabaseManager', 'VoxelDatabase', 'TextureDatabase']