from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

class TextureParams(BaseModel):
    """贴图生成参数模型"""
    voxel_name: str = ""  # 关联的体素名称
    pprompt: str
    nprompt: str = "text, blurry, watermark"
    denoise: float = 1.0

class VoxelTypeParams(BaseModel):
    """体素类型创建参数模型"""
    name: str
    description: str = ""
    texture: str = ""
    is_transparent: bool = False
    # Note: base_color is always [255, 255, 255] in Python, actual color is handled by Unity

class VoxelUpdateParams(BaseModel):
    """体素类型更新参数模型"""
    voxel_id: Optional[int] = None  # 要更新的体素ID
    name: Optional[str] = None  # 要更新的体素名称（如果没有ID）
    new_name: Optional[str] = None  # 新的名称
    description: Optional[str] = None  # 新的描述
    texture: Optional[str] = None  # 新的贴图
    is_transparent: Optional[bool] = None  # 是否透明
    # Note: base_color is always [255, 255, 255] in Python, actual color is handled by Unity

class Command(BaseModel):
    """统一的命令模型"""
    type: str
    params: Union[TextureParams, VoxelTypeParams, VoxelUpdateParams]

class Response(BaseModel):
    """统一的响应模型"""
    session_id: str = Field(default_factory=lambda: f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    answer: str
    commands: List[Command] = [] 