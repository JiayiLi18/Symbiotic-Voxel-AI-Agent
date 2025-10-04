import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PathsConfig:
    voxel_db_path: str
    textures_dir: str


def get_paths_config() -> PathsConfig:
    """集中管理路径：支持从环境变量读取并提供默认值。"""
    voxel_db = os.getenv(
        "VOXEL_DB_PATH",
        r"C:\Users\55485\AppData\LocalLow\DefaultCompany\AI-Agent\VoxelsDB\voxel_definitions.json",
    )
    textures = os.getenv(
        "VOXEL_TEXTURES_DIR",
        r"C:\Aalto\S4\Graduation\AI-Agent\Assets\Resources\VoxelTextures",
    )
    return PathsConfig(voxel_db_path=voxel_db, textures_dir=textures)


