from .manual_prompt import get_relevant_manual_sections
from .context_prompt import generate_context_prompt
from core.models.protocol import EventBatch
from core.models.protocol import PlanPermission

async def generate_executor_system_prompt(plan_permission: PlanPermission) -> str:
    """生成 Executor 的系统提示词"""
    
    # 1. 生成 manual prompt（Executor专用手册）
    manual_prompt = get_relevant_manual_sections([], is_planner=False)
    
    # 2. 生成 context prompt
    context_prompt = await generate_context_prompt(plan_permission)
    
    # 3. 组合所有信息
    return f"""You are an AI Executor for a voxel-based game world.

{manual_prompt}

{context_prompt}

## Your Task
Convert the approved plans into executable commands. Each command must have:
- id: Unique command identifier  
- type: Command type matching the plan's action_type
- params: Specific parameters needed for execution

## Important
- Execute ONLY approved plans, ignore rejected ones
- Generate commands with proper parameters based on game state
- Use directional voxel data for precise positioning
- Extract material names and properties from plan descriptions
- Follow dependency order when generating commands
- Be creative in filling parameter details from descriptions

Return ONLY valid JSON response with commands array."""

async def generate_planner_system_prompt(event_batch: EventBatch) -> str:
    """生成 Planner 的系统提示词 - KISS原则:只负责组装"""
    
    # 1. 生成 manual prompt（根据事件类型选择相关手册，包含planner部分）
    manual_prompt = get_relevant_manual_sections(event_batch.events, is_planner=True)
    
    # 2. 生成 context prompt
    context_prompt = await generate_context_prompt(event_batch)
    
    # 3. 组合所有信息
    return f"""You are an AI Planner for a voxel-based game world.

{manual_prompt}

{context_prompt}
"""