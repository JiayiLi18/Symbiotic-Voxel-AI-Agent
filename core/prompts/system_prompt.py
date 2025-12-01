from .manual_prompt import get_relevant_manual_sections, CORE_SYSTEM
from .context_prompt import generate_context_prompt
from core.models.protocol import EventBatch
from core.models.protocol import PlanPermission

async def generate_executor_system_prompt(plan_permission: PlanPermission) -> str:
    """Generate system prompt for Executor"""
    
    # Extract action types from approved plans to filter manual sections
    action_types = []
    if plan_permission.approved_plans:
        action_types = list(set(plan.action_type for plan in plan_permission.approved_plans))

    # 1. Generate manual prompt (Executor-specific manual)
    manual_prompt = get_relevant_manual_sections([], is_planner=False, use_compact=False, action_types=action_types)
    
    # 2. Generate context prompt (executor mode: is_planner=False, no history)
    context_prompt = await generate_context_prompt(plan_permission, is_planner=False)
    
    # 3. Combine all information
    return f"""You are an AI Executor for a voxel-based game world.

{manual_prompt}

{context_prompt}
"""

async def generate_planner_system_prompt(event_batch: EventBatch) -> str:
    """Generate system prompt for Planner - KISS principle: only responsible for assembly"""
    
    # 1. Generate manual prompt (select relevant manual sections based on event types, including planner section)
    manual_prompt = get_relevant_manual_sections(event_batch.events, is_planner=True, use_compact=False)
    
    # 2. Generate context prompt (planner mode: is_planner=True, includes history)
    context_prompt = await generate_context_prompt(event_batch, is_planner=True)
    
    # 3. Combine all information
    return f"""{manual_prompt}

{context_prompt}
"""