from .manual_prompt import VOXEL_AGENT_MANUAL, get_relevant_manual_sections
from .context_prompt import generate_context_prompt

def generate_system_prompt(
    game_state: 'GameState' = None,
    session_state: 'SessionState' = None,
    context: dict = None
) -> str:
    """生成完整的系统提示词，包含上下文信息"""
    
    base_prompt = """You are an AI assistant specialized in Minecraft-style voxel world creation and management.
Your main responsibilities are:
1. Help users create and modify voxels
2. Generate appropriate textures
3. Build structures
4. Remember important user preferences and themes

Available tools:
{available_tools}
"""

    # 添加相关的手册部分
    if context:
        manual_sections = get_relevant_manual_sections(context)
    else:
        manual_sections = VOXEL_AGENT_MANUAL  # 如果没有上下文，使用完整手册

    # 添加上下文信息（如果有）
    context_info = ""
    if game_state and session_state:
        context_info = f"""
Current Context:
{generate_context_prompt(game_state, session_state)}
"""
    
    return f"""
{base_prompt}

{manual_sections}

{context_info}

When responding:
1. Analyze the user's request carefully
2. Consider the current game state and context
3. Use appropriate tools to fulfill the request
4. Keep track of important information
"""