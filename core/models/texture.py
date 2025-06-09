from pydantic import BaseModel

class TextureParams(BaseModel):
    """贴图生成参数模型"""
    voxel_name: str = ""
    pprompt: str
    nprompt: str = "text, blurry, watermark"
    denoise: float = 1.0