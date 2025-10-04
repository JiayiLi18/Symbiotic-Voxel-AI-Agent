from typing import Tuple
import os
from PIL import Image
import logging

# 输出目录由集中配置提供
try:
    from core.tools.config import get_paths_config
    _OUTPUT_DIR = get_paths_config().textures_dir
except Exception:
    _OUTPUT_DIR = os.path.abspath(os.path.join(os.getcwd(), "textures"))

logger = logging.getLogger(__name__)

def _rgb_to_filename(rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"{r}+{g}+{b}.png"

def _filename_to_rgb(filename: str) -> Tuple[int, int, int]:
    """从文件名中解析 RGB，期望格式为 "R+G+B.png" 或 "R+G+B"。
    解析失败将抛出 ValueError。
    """
    name = os.path.splitext(os.path.basename(filename))[0]
    parts = name.split('+')
    if len(parts) != 3:
        raise ValueError(f"Invalid color filename format: {filename}")
    r, g, b = (int(parts[0]), int(parts[1]), int(parts[2]))
    if not all(0 <= v <= 255 for v in (r, g, b)):
        raise ValueError(f"RGB values out of range in: {filename}")
    return (r, g, b)

def ensure_solid_color_texture(rgb: Tuple[int, int, int], size: int = 16) -> str:
    """生成纯色纹理文件（如果不存在），返回文件名。
    文件将保存到与 TextureGenerator 相同的输出目录。
    """
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    filename = _rgb_to_filename(rgb)
    output_path = os.path.join(_OUTPUT_DIR, filename)

    # 如果文件已存在，直接复用
    if os.path.exists(output_path):
        logger.debug(f"Solid color texture already exists: {output_path}")
        return filename

    # 尝试在输出目录查找任何命名变体（例如缺少.png）
    alt_output_path = os.path.join(_OUTPUT_DIR, os.path.splitext(filename)[0])
    if os.path.exists(alt_output_path):
        logger.debug(f"Found color texture variant: {alt_output_path}")
        return filename

    # 真正生成
    image = Image.new("RGB", (size, size), rgb)
    image.save(output_path, format="PNG")
    logger.info(f"Generated solid color texture: {output_path}")

    return filename

def ensure_solid_color_texture_from_name(filename: str, size: int = 16) -> str:
    """根据文件名解析颜色并确保对应纯色 PNG 存在，返回规范化文件名（R+G+B.png）。"""
    rgb = _filename_to_rgb(filename)
    return ensure_solid_color_texture(rgb, size=size)


