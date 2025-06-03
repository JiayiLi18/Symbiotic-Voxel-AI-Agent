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
    base_color: str = "#FFFFFF"
    description: str = ""

class FillDBParams(BaseModel):
    """数据库填充参数模型"""
    section: str
    content: str

class Command(BaseModel):
    """统一的命令模型"""
    type: str
    params: Union[TextureParams, VoxelTypeParams, FillDBParams]

class Response(BaseModel):
    """统一的响应模型"""
    session_id: str = Field(default_factory=lambda: f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    answer: str
    commands: List[Command] = [] 