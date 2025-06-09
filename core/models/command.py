from pydantic import BaseModel, Field
from typing import Union, List
from datetime import datetime
from core.models.texture import TextureParams
from core.models.voxel import VoxelTypeParams, VoxelUpdateParams


class Command(BaseModel):
    """统一的命令模型"""
    type: str
    params: Union[TextureParams, VoxelTypeParams, VoxelUpdateParams]

class Response(BaseModel):
    """统一的响应模型"""
    session_id: str = Field(
        default_factory=lambda: f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    answer: str
    commands: List[Command] = []