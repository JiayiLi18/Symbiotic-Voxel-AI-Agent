from enum import Enum
from typing import Optional, List, Dict, Literal, Union
from pydantic import BaseModel, field_validator
from core.models.base import VoxelFace

class TextureRequest(BaseModel):
    """纹理生成请求 - 核心四个参数"""
    pprompt: str  # 正面提示词
    nprompt: str = "text, blurry, watermark"  # 负面提示词
    reference_image: Optional[str] = None  # 参考图片文件名

class TextureJobRequest(BaseModel):
    """贴图生成请求 - 简化版本，专注于核心参数"""
    voxel_name: str  # 体素名称，用于标识这个纹理是给哪个voxel用的
    faces: List[VoxelFace] = [VoxelFace.FRONT]  # 要生成纹理的面列表
    pprompt: str  # 正面提示词
    nprompt: str = "text, blurry, watermark"  # 负面提示词
    reference_image: Optional[str] = None  # 参考图片文件名

    @property
    def texture_name(self) -> str:
        """生成纹理文件名：如果是所有面则只用voxel_name，否则加上面的后缀"""
        all_faces = set(VoxelFace)
        current_faces = set(self.faces)
        
        if current_faces == all_faces:
            # 所有面都用这个纹理，不加后缀
            return self.voxel_name
        elif len(self.faces) == 1:
            # 单个面，加上面的后缀
            return f"{self.voxel_name}-{self.faces[0].value}"
        else:
            # 多个面但不是全部，用面的组合作为后缀
            face_names = sorted([face.value for face in self.faces])
            return f"{self.voxel_name}-{'_'.join(face_names)}"

    @field_validator('faces')
    @classmethod
    def validate_faces(cls, faces: List[Union[VoxelFace, str]]) -> List[VoxelFace]:
        """验证并转换面列表"""
        result = []
        for face in faces:
            if isinstance(face, str):
                result.append(VoxelFace.from_str(face))
            else:
                result.append(face)
        return result

class TextureJobAck(BaseModel):
    """贴图生成任务确认"""
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    error: Optional[str] = None