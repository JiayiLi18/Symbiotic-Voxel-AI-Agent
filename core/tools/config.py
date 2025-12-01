import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PathsConfig:
    textures_dir: str


def get_paths_config() -> PathsConfig:
    """集中管理路径：支持从环境变量读取并提供默认值。"""
    textures = os.getenv(
        "VOXEL_TEXTURES_DIR",
        r"C:\Aalto\S4\Graduation\AI-Agent\Assets\Resources\VoxelTextures",
    )
    return PathsConfig(textures_dir=textures)


