from pydantic import BaseModel
from typing import Optional

class VoxelTypeParams(BaseModel):
    """体素类型创建参数模型"""
    name: str
    description: str = ""
    texture: str = ""
    is_transparent: bool = False

class VoxelUpdateParams(BaseModel):
    """体素类型更新参数模型"""
    voxel_id: Optional[int] = None
    name: Optional[str] = None
    new_name: Optional[str] = None
    description: Optional[str] = None
    texture: Optional[str] = None
    is_transparent: Optional[bool] = None