#!/usr/bin/env python3
"""
简单的TextureGenerator测试脚本
从项目根目录运行
"""

import asyncio
import logging
from core.tools.texture.texture_generator import TextureGenerator

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def simple_test():
    """简单测试"""
    print("🚀 开始简单测试...")
    
    generator = TextureGenerator()
    
    try:
        # 测试工作流加载
        workflow = generator._load_workflow()
        print(f"✅ 工作流加载成功，包含 {len(workflow)} 个节点")
        
        # 测试工作流配置
        configured_workflow = generator._configure_workflow(
            workflow.copy(),
            "stone texture",
            "text, blurry, watermark",
            None
        )
        print("✅ 工作流配置成功")
        print(f"   节点3 latent_image: {configured_workflow['3']['inputs']['latent_image']}")
        print(f"   节点3 denoise: {configured_workflow['3']['inputs']['denoise']}")
        
        # 测试纹理生成（如果ComfyUI服务器运行的话）
        print("\n🧪 尝试生成纹理...")
        result = await generator.generate_texture(
            tex_name="test_simple",
            pprompt="rough stone texture",
            nprompt="text, blurry, watermark"
        )
        
        if result:
            print(f"✅ 纹理生成成功! 文件: {result}")
        else:
            print("❌ 纹理生成失败")
            
    except Exception as e:
        print(f"❌ 测试出错: {str(e)}")
        logger.error(f"测试失败: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(simple_test())
