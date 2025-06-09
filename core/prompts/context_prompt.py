def generate_context_prompt(
    game_state: 'GameState',
    session_state: 'SessionState'
) -> str:
    """生成上下文提示词"""
    
    # 游戏状态信息
    game_context = f"""- Player position: {game_state.player_position}
- Nearby voxels: {game_state.get_surrounding_voxels(radius=5)}"""

    # 会话状态信息
    session_context = f"""- Current theme: {session_state.current_theme or 'Not set'}
- Important preferences: {[info.content for info in session_state.important_info if info.category == 'preference']}
- Current goals: {[info.content for info in session_state.important_info if info.category == 'goal']}"""

    return f"{game_context}\n{session_context}"