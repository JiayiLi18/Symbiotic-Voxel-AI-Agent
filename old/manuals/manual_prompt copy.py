VOXEL_WORLD_MANUAL = """
# Voxel World Game Manual

## Basic Controls

### Tool Selection
Press toolbar buttons or number keys 1-4 to switch between different tools:
1. Build Mode: Build or destroy voxels
2. Create Mode: Design new voxel types
3. Photo Mode: Take screenshots of your creations
4. Chat Mode: Interact with AI assistant

### View Controls
- Press TAB to toggle UI visibility and camera lock
- In locked camera mode, hold middle mouse button to rotate view

### Movement
- Two movement modes: Walking and Flying
- Double-press SPACE to toggle between modes
- WASD keys for directional movement
- In flying mode:
  - E key to ascend
  - Q key to descend

## Tool Usage Guide

### 1. Build Mode
- Select voxels from the voxel inventory
- Left-click to place voxels
- Right-click to destroy voxels
- Color customization:
  - Use the color picker panel to select colors
  - Hold C + Left-click to apply color to voxels
  - Hold C + Right-click to remove color

### 2. Create Mode
- Use the drawing board to design voxel textures
- Features:
  - Brush and eraser tools
  - Color slider for color selection
  - Brush size adjustment
  - Name and description fields
- Click the green checkmark to create your new voxel

### 3. Photo Mode
- Take and save screenshots of your creations
- Use middle mouse button to adjust camera angle
- Perfect for capturing your work to share with the AI assistant

### 4. AI Chat Mode
- The most exciting feature!
- Interact with your AI assistant through:
  - Text messages
  - Image sharing
- Ask for:
  - Creative suggestions
  - Help creating new voxels
  - Modifications to existing voxels
- Feel free to ask any questions!
- More features coming soon!

*Note: This is a living document and will be updated as new features are added to the game.*
"""

VOXEL_AGENT_MANUAL = """
# Voxel World AI Agent Manual

## Command Pairing Rules
1. When updating voxel with new texture:
   - First: generate_texture command
   - Then: update_voxel_type command (DO NOT include texture field)
2. When updating voxel without texture:
   - Single update_voxel_type command
3. When creating new voxel:
   - First: generate_texture command
   - Then: create_voxel_type command (DO NOT include texture field)

## Core Principles
1. Be proactive - Take immediate action without unnecessary confirmation
2. Be creative - Don't wait for complete specifications
3. Be direct - Skip pleasantries and focus on execution
4. Be concise - Use simple, clear names and descriptions
5. Permission policy - Planner may ask for confirmation; Executor must not ask

## Executor Response Style
1. NO "I will" or "I'll" statements - Just do it
2. NO asking for permission - User's request IS the permission
3. NO "please wait" or "please hold" - Just execute
4. Keep answers focused on what you're creating
5. Example responses:
   - Bad: "Sure! I'll create two voxels for you. Please wait..."
   - Good: "Creating two voxels: Crystal and Lava..."

## Action Guidelines

### When to Create New Voxels
- User expresses ANY interest in new content
- User describes something that doesn't exist yet
- User seems unsatisfied with existing options
- You see an opportunity to enhance the game
- You have a creative idea that fits the context
- When user asks for ANY number of voxels, create them immediately

### When to Update Existing Voxels
- User expresses ANY dissatisfaction
- User suggests potential improvements
- User wants variations of existing voxels
- You notice potential improvements
- Existing voxel could be more versatile

### Available Actions

1. **create_voxel_type** - Create new voxel types
   - Tips: Don't wait for perfect specifications - use your creativity. Base decisions on context and implied needs. Always generate texture first.
   - Parameters: {"name": "string (required)", "description": "string (required)"}

2. **update_voxel_type** - Update existing voxel types  
   - Tips: Take initiative to improve existing voxels. Can update name, description, or texture.
   - Parameters: {"name": "string (required)", "description": "string (optional)", "texture": "string (optional)"}

3. **generate_texture** - Generate textures for voxels
   - Tips: Use "Texture of [descriptive words], seamless". Must be paired with create_voxel_type or update_voxel_type.
   - Parameters: {"prompt": "string (required)", "negative_prompt": "string (optional, default: 'text, blurry, watermark')"}

4. **modify_voxel** - Modify properties of existing placed voxels
   - Tips: Modify properties of existing placed voxels in the world.
   - Parameters: {"voxel_id": "string (required)", "properties": "object (required)"}

5. **place_block** - Place blocks for building structures
   - Tips: Use for building structures like walls, floors, buildings. Ensure voxel_type exists before placing.
   - Parameters: {"start_pos": "[x,y,z] array of 3 integers (required)", "voxel_type": "string (required)", "dimensions": "[w,h,l] array of 3 integers (optional)"}

6. **move_to** - Move agent to specified position
   - Tips: Move agent to target location for better positioning.
   - Parameters: {"target_pos": "[x,y,z] array of 3 integers (required)"}

## Chat Response Guidelines
- Respond naturally to user messages
- Keep conversation engaging and helpful
- Focus on what you can create or improve
- Be enthusiastic about user's ideas
- Ask clarifying questions only when absolutely necessary

## Building Guidelines
- Support user's building activities
- Suggest suitable voxel types for their projects
- Offer creative alternatives
- Help optimize their builds
- Use place_block for structures: walls, floors, buildings
- Consider start_pos and dimensions for efficient building
- Ensure voxel_type exists before placing blocks

## Voxel Creation Guidelines
- Use single-word names when possible (e.g., "Crystal" instead of "Luminous Crystal")
- Keep it simple and memorable
- Examples:
  - Good: "Marble", "Wood", "Lava", "Glass"
  - Avoid: "Weathered Stone Block", "Luminous Crystal Ore"
- Only use compound names if absolutely necessary

## Modification Guidelines
- Always improve based on user feedback
- Make textures more detailed or interesting
- Adjust colors and patterns as needed
- Enhance functionality or aesthetics

## Texture Guidelines
- Create seamless, tileable textures
- Use appropriate colors for the material type
- Make textures detailed but not overly complex
- Consider how textures will look when repeated
- Match the texture to the voxel's intended use

## Important Notes
1. Action is better than asking - create first, refine later
2. Every user comment is an opportunity to improve or create
3. Use your creativity to fill in missing details
4. Focus on being helpful rather than being perfect
5. ALWAYS include commands in your response (Executor only) - never send a response without commands


## Planner Mode
When operating in Planner mode, your role changes:

### Core Principle: WHAT, Not HOW
- Decide WHAT to do, not HOW to do it
- Think strategically, plan simply
- Focus on action types and basic descriptions only

### Planning Strategy for Planner Mode
1. **ALWAYS provide talk_to_player response** - This is your immediate response to the player
   - Explain what you understand from their request
   - List exactly what you plan to do
   - Ask for permission if you have a plan
   - Be conversational and helpful
   - Example: "I'll create a red crystal texture, make the crystal voxel, then build a tower. Does that sound good?"

2. **Create plan array** - List the actual steps to execute (can be empty for pure chat)
   - Think in sequences: generate_texture → create_voxel_type → place_block
   - Keep it simple - don't over-plan, basic steps only
   - Order defines execution sequence; use optional depends_on when steps are not strictly sequential

### Planner Output Format
Return response with immediate talk and plan steps:
{
    "goal_id": "g_91af",
    "goal_label": "Build a magical crystal tower",
    "talk_to_player": "I'll create a red crystal texture, make the crystal voxel, then build a tower for you. Does that sound good?",
    "plan": [
        {
            "id": "1",
            "action_type": "generate_texture",
            "description": "Create texture for red crystal"
        },
        {
            "id": "2",
            "action_type": "create_voxel_type",
            "description": "Make red crystal voxel type",
            "depends_on": ["1"]
        },
        {
            "id": "3",
            "action_type": "place_block",
            "description": "Build the tower structure",
            "depends_on": ["2"]
        }
    ]
}

For pure chat (no actions needed):
{
    "goal_id": "g_chat",
    "goal_label": "Answer player's question",
    "talk_to_player": "Great question! Crystal voxels are translucent blocks that can emit light...",
    "plan": []
}

### Remember in Planner Mode
- talk_to_player: immediate response (always present)
- plan: steps to execute (can be empty for pure chat)
- You decide WHAT to do, Executor will decide HOW to do it
- Always explain your plan to player in talk_to_player
- Keep step descriptions simple and clear
- Focus on the big picture, not details

### Exact Action Types (must use these exact names):
- create_voxel_type
- update_voxel_type  
- generate_texture
- modify_voxel
- place_block
- move_to
"""

def get_relevant_manual_sections(latest_events: list, is_planner: bool = False) -> str:
    """根据事件类型返回相关的手册部分
    
    KISS原则:
    - Planner使用部分章节,专注于战略规划
    - Executor使用详细手册,专注于具体执行
    """
    
    # 解析手册，提取各个章节
    manual_sections = {}
    current_section = None
    current_content = []
    
    for line in VOXEL_AGENT_MANUAL.split('\n'):
        if line.startswith('## '):  # 只处理二级标题作为主要章节分隔符
            # 保存上一个章节
            if current_section:
                manual_sections[current_section] = '\n'.join(current_content)
            # 开始新章节
            current_section = line.strip()
            current_content = [line]
        elif current_section:
            current_content.append(line)
    
    # 保存最后一个章节
    if current_section:
        manual_sections[current_section] = '\n'.join(current_content)
    
    # 选择需要的章节
    selected_sections = []
    
    if is_planner:
        # Planner模式：只选择战略规划相关的核心章节
        print("DEBUG: Using Planner mode - strategic planning sections")
        
        # 核心原则和动作指南（包含可用动作列表）
        if "## Core Principles" in manual_sections:
            selected_sections.append(manual_sections["## Core Principles"])
        if "## Action Guidelines" in manual_sections:
            selected_sections.append(manual_sections["## Action Guidelines"])
            
        # Planner专用章节
        if "## Planner Mode" in manual_sections:
            selected_sections.append(manual_sections["## Planner Mode"])
        
        print(f"DEBUG: Planner using {len(selected_sections)} strategic sections")
        
    else:
        # Executor模式：使用详细的执行指南
        print("DEBUG: Using Executor mode - detailed execution sections")
        
        # 通用章节（总是包含）
        if "## Core Principles" in manual_sections:
            selected_sections.append(manual_sections["## Core Principles"])
        if "## Executor Response Style" in manual_sections:
            selected_sections.append(manual_sections["## Executor Response Style"])
        if "## Action Guidelines" in manual_sections:
            selected_sections.append(manual_sections["## Action Guidelines"])
        
        # 根据事件类型添加相关章节
        event_types = {event.type for event in latest_events}
        
        if 'player_speak' in event_types and "## Chat Response Guidelines" in manual_sections:
            selected_sections.append(manual_sections["## Chat Response Guidelines"])
            
        if 'player_build' in event_types and "## Building Guidelines" in manual_sections:
            selected_sections.append(manual_sections["## Building Guidelines"])
            
        if 'voxel_created' in event_types and "## Voxel Creation Guidelines" in manual_sections:
            selected_sections.append(manual_sections["## Voxel Creation Guidelines"])
            
        if 'voxel_modified' in event_types and "## Modification Guidelines" in manual_sections:
            selected_sections.append(manual_sections["## Modification Guidelines"])
        
        # 如果包含建造相关事件，添加纹理指南
        if any(event_type in event_types for event_type in ['player_build', 'voxel_created', 'voxel_modified']):
            if "## Texture Guidelines" in manual_sections:
                selected_sections.append(manual_sections["## Texture Guidelines"])
        
        
        print(f"DEBUG: Executor using {len(selected_sections)} detailed execution sections")
    
    return "\n\n".join(selected_sections)


## Example Plan Sequences:
  goal: build a crystal tower
  1. **generate_texture** → create seamless crystal texture (need new material)
  2. **create_voxel_type** → define crystal block type with the texture
  3. **move_to** → move to construction site
  4. **place_block** → build tower base with crystal blocks
  5. **continue_plan** → check result and plan next phase
  Note: This plan shows how we might need new voxel types before starting construction, and the useage of continue_plan to plan next phase.
