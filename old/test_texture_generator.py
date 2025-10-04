#!/usr/bin/env python3
"""
TextureGenerator 测试文件
用于测试纹理生成功能是否正常工作
"""

import asyncio
import logging
import os
import sys

# 添加项目根目录到Python路径（现在文件就在根目录）
sys.path.append(os.path.dirname(__file__))

from core.tools.texture.texture_generator import TextureGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_basic_texture_generation():
    """测试基本纹理生成功能"""
    print("=" * 60)
    print("🧪 测试基本纹理生成功能")
    print("=" * 60)
    
    generator = TextureGenerator()
    
    # 测试参数
    test_cases = [
        {
            "name": "测试1: 无参考图片的纹理生成",
            "tex_name": "test_stone",
            "pprompt": "rough stone texture with cracks and weathering",
            "nprompt": "text, blurry, watermark",
            "reference_image": None
        },
        {
            "name": "测试2: 有参考图片的纹理生成",
            "tex_name": "test_wood",
            "pprompt": "wooden plank texture with natural grain",
            "nprompt": "text, blurry, watermark",
            "reference_image": "test_face.png"  # 假设有这个参考图片
        },
        {
            "name": "测试3: 简单提示词测试",
            "tex_name": "test_wood",
            "pprompt": "wooden plank texture with natural grain",
            "nprompt": "text, blurry, watermark",
            "reference_image": None
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 {test_case['name']}")
        print(f"   纹理名称: {test_case['tex_name']}")
        print(f"   正面提示词: {test_case['pprompt']}")
        print(f"   参考图片: {test_case['reference_image'] or '无'}")
        
        try:
            result = await generator.generate_texture(
                tex_name=test_case['tex_name'],
                pprompt=test_case['pprompt'],
                nprompt=test_case['nprompt'],
                reference_image=test_case['reference_image']
            )
            
            if result:
                print(f"   ✅ 成功! 生成的纹理文件: {result}")
            else:
                print(f"   ❌ 失败! 没有生成纹理文件")
                
        except Exception as e:
            print(f"   ❌ 错误: {str(e)}")
            logger.error(f"测试 {i} 失败: {str(e)}", exc_info=True)

async def test_edge_cases():
    """测试边界情况"""
    print("\n" + "=" * 60)
    print("🧪 测试边界情况")
    print("=" * 60)
    
    generator = TextureGenerator()
    
    edge_cases = [
        {
            "name": "边界测试1: 空提示词",
            "tex_name": "test_empty",
            "pprompt": "",
            "nprompt": "text, blurry, watermark",
            "reference_image": None,
            "should_fail": True
        },
        {
            "name": "边界测试2: 很长的提示词",
            "tex_name": "test_long",
            "pprompt": "very detailed and complex texture with many elements including stones, moss, cracks, weathering, natural aging, organic patterns, intricate details, high resolution, photorealistic, professional quality",
            "nprompt": "text, blurry, watermark",
            "reference_image": None,
            "should_fail": False
        },
        {
            "name": "边界测试3: 特殊字符文件名",
            "tex_name": "test-special_chars!@#",
            "pprompt": "metal texture",
            "nprompt": "text, blurry, watermark",
            "reference_image": None,
            "should_fail": False
        }
    ]
    
    for i, test_case in enumerate(edge_cases, 1):
        print(f"\n📋 {test_case['name']}")
        print(f"   纹理名称: {test_case['tex_name']}")
        print(f"   正面提示词: {test_case['pprompt'][:50]}{'...' if len(test_case['pprompt']) > 50 else ''}")
        
        try:
            result = await generator.generate_texture(
                tex_name=test_case['tex_name'],
                pprompt=test_case['pprompt'],
                nprompt=test_case['nprompt'],
                reference_image=test_case['reference_image']
            )
            
            if result:
                if test_case['should_fail']:
                    print(f"   ⚠️  意外成功! 生成的纹理文件: {result}")
                else:
                    print(f"   ✅ 成功! 生成的纹理文件: {result}")
            else:
                if test_case['should_fail']:
                    print(f"   ✅ 正确失败! 没有生成纹理文件")
                else:
                    print(f"   ❌ 意外失败! 没有生成纹理文件")
                    
        except Exception as e:
            if test_case['should_fail']:
                print(f"   ✅ 正确抛出异常: {str(e)}")
            else:
                print(f"   ❌ 意外错误: {str(e)}")
                logger.error(f"边界测试 {i} 失败: {str(e)}", exc_info=True)

async def test_workflow_configuration():
    """测试工作流配置"""
    print("\n" + "=" * 60)
    print("🧪 测试工作流配置")
    print("=" * 60)
    
    generator = TextureGenerator()
    
    try:
        # 测试工作流加载
        workflow = generator._load_workflow()
        print("✅ 工作流加载成功")
        print(f"   工作流包含 {len(workflow)} 个节点")
        
        # 测试工作流配置（无参考图片）
        configured_workflow = generator._configure_workflow(
            workflow.copy(),
            "test prompt",
            "negative prompt",
            None
        )
        print("✅ 无参考图片的工作流配置成功")
        print(f"   节点3 latent_image: {configured_workflow['3']['inputs']['latent_image']}")
        print(f"   节点3 denoise: {configured_workflow['3']['inputs']['denoise']}")
        print(f"   节点58 strength: {configured_workflow['58']['inputs']['strength']}")
        
        # 测试工作流配置（有参考图片）
        configured_workflow_with_ref = generator._configure_workflow(
            workflow.copy(),
            "test prompt with reference",
            "negative prompt",
            "test_reference.png"
        )
        print("✅ 有参考图片的工作流配置成功")
        print(f"   节点3 latent_image: {configured_workflow_with_ref['3']['inputs']['latent_image']}")
        print(f"   节点3 denoise: {configured_workflow_with_ref['3']['inputs']['denoise']}")
        print(f"   节点58 strength: {configured_workflow_with_ref['58']['inputs']['strength']}")
        
    except Exception as e:
        print(f"❌ 工作流配置测试失败: {str(e)}")
        logger.error(f"工作流配置测试失败: {str(e)}", exc_info=True)

def check_environment():
    """检查环境配置"""
    print("=" * 60)
    print("🔍 检查环境配置")
    print("=" * 60)
    
    # 检查工作流文件 - 现在文件就在根目录
    workflow_path = "Minecraft Texture Workflow v2.json"
    if os.path.exists(workflow_path):
        print(f"✅ 工作流文件存在: {workflow_path}")
    else:
        print(f"❌ 工作流文件不存在: {workflow_path}")
    
    # 检查输入目录
    input_dir = r"C:\Aalto\S4\Graduation\AI-Agent\Assets\Resources\VoxelTextures"
    if os.path.exists(input_dir):
        print(f"✅ 输入目录存在: {input_dir}")
    else:
        print(f"❌ 输入目录不存在: {input_dir}")
    
    # 检查输出目录
    output_dir = r"C:\Aalto\S4\Graduation\AI-Agent\Assets\Resources\VoxelTextures"
    if os.path.exists(output_dir):
        print(f"✅ 输出目录存在: {output_dir}")
    else:
        print(f"❌ 输出目录不存在: {output_dir}")
    
    # 检查ComfyUI服务器连接
    import requests
    try:
        response = requests.get("http://127.0.0.1:8188/system_stats", timeout=5)
        if response.status_code == 200:
            print("✅ ComfyUI服务器连接正常")
        else:
            print(f"⚠️  ComfyUI服务器响应异常: {response.status_code}")
    except Exception as e:
        print(f"❌ ComfyUI服务器连接失败: {str(e)}")
        print("   请确保ComfyUI服务器在 127.0.0.1:8188 上运行")

async def main():
    """主测试函数"""
    print("🚀 TextureGenerator 测试开始")
    print("=" * 60)
    
    # 检查环境
    check_environment()
    
    # 测试工作流配置
    await test_workflow_configuration()
    
    # 测试基本功能
    await test_basic_texture_generation()
    
    # 测试边界情况
    await test_edge_cases()
    
    print("\n" + "=" * 60)
    print("🏁 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())
