import os
from core.models.protocol import EventBatch, PlanPermission
from core.models.game_state import GameState
from typing import Optional, List, Union

# 工具引用 - 从main.py获取
def get_tools():
    """获取工具实例"""
    from api.main import session_manager
    from core.tools.voxel.manager import VoxelManager
    from core.tools.config import get_paths_config
    
    # 创建VoxelManager实例
    cfg = get_paths_config()
    voxel_manager = VoxelManager(cfg.voxel_db_path)
    
    return session_manager, voxel_manager


async def generate_context_prompt(input_data: Union[EventBatch, PlanPermission]) -> str:
    """生成上下文提示词
    
    Args:
        input_data: EventBatch (for planner) or PlanPermission (for executor)
    """
    
    # 获取工具实例
    session_manager, voxel_manager = get_tools()
    
    # 提取基础信息
    session_id = input_data.session_id
    game_state = input_data.game_state
    
    context_parts = []
    
    # 1. 根据输入类型添加特定信息
    if isinstance(input_data, EventBatch):
        # Planner模式：添加事件信息
        if input_data.events:
            context_parts.append("## Events")
            for event in input_data.events:
                event_desc = f"[{event.timestamp}] {event.type}"
                if hasattr(event.payload, 'text'):
                    event_desc += f": {event.payload.text}"
                elif hasattr(event.payload, 'voxel_instance'):
                    voxel = event.payload.voxel_instance
                    event_desc += f": {voxel.voxel_name} at {voxel.position.to_compact_str()}"
                elif hasattr(event.payload, 'nearby_voxels') and event.payload.nearby_voxels:
                    # 处理nearby_voxels，转换为数量统计
                    voxel_stats = _process_nearby_voxels_stats(event.payload.nearby_voxels)
                    event_desc += f": {voxel_stats}"
                context_parts.append(f"- {event_desc}")
        
    elif isinstance(input_data, PlanPermission):
        # Executor模式：添加计划许可信息
        context_parts.append("## Plan Permission")
        context_parts.append(f"- Goal: {input_data.goal_label}")
        
        if input_data.approved_plans:
            context_parts.append("### Approved Plans")
            for plan in input_data.approved_plans:
                depends_info = f" (depends on: {plan.depends_on})" if plan.depends_on else ""
                context_parts.append(f"- [{plan.id}] {plan.action_type}: {plan.description}{depends_info}")
        
        if input_data.additional_info:
            context_parts.append("### Additional Information")
            context_parts.append(f"- {input_data.additional_info}")
    else:
        raise ValueError(f"Unsupported input type: {type(input_data)}")
    
    # 2. 添加游戏状态信息（通用逻辑）
    _add_game_state_section(context_parts, game_state)
    
    # 3. 添加历史信息（通用逻辑）
    _add_history_section(context_parts, session_manager, session_id)
    
    # 4. 添加目标和进度信息
    if game_state:
        _add_goal_status_section(context_parts, game_state)
    
    # 5. 添加可用体素类型信息（通用逻辑）
    await _add_voxel_types_section(context_parts, voxel_manager)
    
    return "\n".join(context_parts)

def _add_game_state_section(context_parts: List[str], game_state: Optional[GameState]) -> None:
    """添加游戏状态部分"""
    if game_state:
        # 计算Player相对于Agent的位置
        player_rel_x = game_state.player_abs_position.x - game_state.agent_abs_position.x
        player_rel_y = game_state.player_abs_position.y - game_state.agent_abs_position.y
        player_rel_z = game_state.player_abs_position.z - game_state.agent_abs_position.z
        player_rel_str = f"({player_rel_x:+d},{player_rel_y:+d},{player_rel_z:+d})"
        
        # 获取方向性体素信息
        directional_info = game_state.get_directional_voxels_info()
        
        context_parts.append(f"""## Game State
- Time: {game_state.timestamp}
- Player Rel Position: {player_rel_str} (relative to Agent)
- Agent Absolute Position: {game_state.agent_abs_position.to_compact_str()}
- Directional Voxels (nearest in each direction):
{directional_info}""")
    else:
        context_parts.append("## Game State\nUnknown - no game state provided")

def _add_history_section(context_parts: List[str], session_manager, session_id: str) -> None:
    """添加历史部分"""
    history = session_manager.get_history(session_id)
    if history:
        context_parts.append("## History")
        for msg in history:
            msg_type = msg.get('type', 'chat')
            context_parts.append(f"- [{msg_type}] {msg['role']}: {msg['content']}")
    else:
        context_parts.append("## History\nNo history yet.")

async def _add_voxel_types_section(context_parts: List[str], voxel_manager) -> None:
    """添加可用体素类型部分"""
    try:
        # 使用VoxelManager获取所有体素类型 - 异步调用
        all_voxels = await voxel_manager.get_all_voxels()
        if all_voxels:
            context_parts.append("## Voxel Types")
            for voxel in all_voxels[:64]:  # 限制显示数量
                desc = f" - {voxel.description}" if voxel.description else ""
                context_parts.append(f"- {voxel.name} (ID: {voxel.id}){desc}")
        else:
            context_parts.append("## Voxel Types\nNo types available.")
    except Exception as e:
        context_parts.append(f"## Voxel Types\nDatabase error: {str(e)}")


def _process_nearby_voxels_stats(nearby_voxels) -> str:
    """处理nearby_voxels，转换为数量统计格式"""
    if not nearby_voxels:
        return "no nearby voxels"
    
    # 统计每种体素类型的数量
    voxel_counts = {}
    for voxel in nearby_voxels:
        voxel_name = voxel.voxel_name if hasattr(voxel, 'voxel_name') else voxel.get('voxel_name', 'Unknown')
        voxel_counts[voxel_name] = voxel_counts.get(voxel_name, 0) + 1
    
    # 格式化为 "name1*count1, name2*count2" 的形式
    stats_parts = []
    for name, count in sorted(voxel_counts.items()):
        stats_parts.append(f"{name}*{count}")
    
    return f"nearby voxels: {', '.join(stats_parts)}"

def _format_command_params_compact(params) -> str:
    """将命令参数格式化为紧凑字符串，特别处理Position对象"""
    if isinstance(params, dict):
        compact_params = {}
        for key, value in params.items():
            if isinstance(value, dict) and all(k in value for k in ['x', 'y', 'z']):
                # 这是一个Position对象的字典表示
                compact_params[key] = f"({value['x']},{value['y']},{value['z']})"
            else:
                compact_params[key] = value
        return str(compact_params)
    else:
        return str(params)

def _add_goal_status_section(context_parts: List[str], game_state: GameState) -> None:
    """添加目标状态部分"""
    
    if not game_state.pending_plans and not game_state.last_commands:
        return
    
    context_parts.append("## Goals")
    
    # 按goal_id分组
    goals_dict = {}
    
    # 收集pending plans
    for plan in game_state.pending_plans:
        goal_id = plan.goal_id or "unknown"
        if goal_id not in goals_dict:
            goals_dict[goal_id] = {"plans": [], "commands": []}
        goals_dict[goal_id]["plans"].append(plan)
    
    # 收集last commands
    for command in game_state.last_commands:
        goal_id = command.goal_id or "unknown"
        if goal_id not in goals_dict:
            goals_dict[goal_id] = {"plans": [], "commands": []}
        goals_dict[goal_id]["commands"].append(command)
    
    # 按goal输出
    for goal_id, goal_data in goals_dict.items():
        context_parts.append(f"\n### {goal_id}")
        
        # Plans
        if goal_data["plans"]:
            context_parts.append("**Plans:**")
            for plan in goal_data["plans"]:
                depends_info = f" (dep: {plan.depends_on})" if plan.depends_on else ""
                context_parts.append(f"- [{plan.id}] {plan.action_type}: {plan.description}{depends_info}")
        
        # Commands
        if goal_data["commands"]:
            context_parts.append("**Commands:**")
            recent_commands = goal_data["commands"][-3:]
            for command in recent_commands:
                phase_info = f" [{command.phase}]" if command.phase else ""
                compact_params = _format_command_params_compact(command.params)
                context_parts.append(f"- [{command.id}] {command.type}{phase_info}: {compact_params}")