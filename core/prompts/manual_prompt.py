VOXEL_WORLD_MANUAL = """
# Voxel World Game Manual

## Basic Controls
[...省略手册内容...]
"""

VOXEL_AGENT_MANUAL = """
# Voxel World AI Agent Manual

## Command Pairing Rules
[...省略手册内容...]
"""

def get_relevant_manual_sections(context: dict) -> str:
    """根据上下文返回相关的手册部分"""
    sections = []
    
    # 如果涉及到voxel创建或修改
    if context.get('needs_voxel_operation'):
        sections.append("## Command Pairing Rules")
        sections.append("## Action Guidelines")
    
    # 如果涉及到命名
    if context.get('needs_naming'):
        sections.append("## Naming Guidelines")
    
    # 如果是一般性交互
    sections.append("## Core Principles")
    sections.append("## Response Style")
    
    return "\n\n".join(sections)