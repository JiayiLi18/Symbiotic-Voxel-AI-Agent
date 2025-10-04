# =============================================================================
# 共用手册部分 - 基础概念和通用理解
# =============================================================================
COMMON_MANUAL = """
# Voxel World Common Manual

## World & Coordinates
- **World**: 50x50x50 3D voxel (blocks) world, the user and agent co-create the world.
- **Timestamp**: World time (hhmmss format)
- **Positions**: Agent uses absolute coordinates; Player position is relative to the Agent.
- **Directional Voxels**: Six directions around the Agent showing nearest voxels
    - **SPACE RELATIONS**: When user asks "around you", they mean around ME (the agent)
    - **Axes**: x = left/right (+x = right), y = front/back (+y = front), z = up/down (+z = up)
    - **Six-Direction Rays** (max 10 blocks): return nearest non-empty voxel per direction (name/ID/distance). 
    - Distance 1 = adjacent; 2+ = with gap
    - Examples: `front: empty (distance: 10)`; `up: stone (id:3, distance:2)`
- **Nearby Voxels (5x5x5)**: Report format: `nearby voxels: Dirt*3, Leaves*2, Stone*1`
    - Used with images to understand context; **does not replace precise coordinates**.  

## Perception & Images
- **Player Images**: unknown location; **do not build directly** from them; use for feedback/suggestions; ask player to move closer or provide an Agent snapshot if building is needed.  
- **Agent Images**: complement six-direction data; good for spatial context and estimating counts; **precise coordinates still rely on six-direction rays**.  

## Goals & Progress
- **Pending Plans**: What remains to do (id, action_type, description, depends_on)
- **Last Commands**: Recent execution attempts (id, type, params, phase: succeed/ongoing/failed)

## Voxel Types
- Unique ID (number) + name (string) + description
- Stats and sensors often show IDs; **commands reference names**.

## Plan / Command Types
- **Basic Actions**:
  - **create_voxel_type**: Define new voxel type
  - **update_voxel_type**: Modify existing voxel type
  - **place_block**: Build structures with voxels
  - **destroy_block**: Remove voxels from world
  - **move_to**: Move agent to position
  - **continue_plan**: Signal that more planning is needed

## Build & Move Commands
- **place_block**: direction + distance(start from Agent) + count(consecutive)
- **destroy_block**: same schema, the block could be filtered by voxel_name and voxel_id (optional)
- **move_to**: relative (x/y/z) movement, Agent-centric
- Example: `front, distance=1, count=3` → place 3 consecutive blocks starting 1 block ahead.
"""

# =============================================================================
# Planner专用手册部分 - 规划原则和响应要求
# =============================================================================
PLANNER_MANUAL = """
# Voxel World Planner Manual

## Core Principles
- Decide **WHAT** to do, not **HOW**.
- Check history and unfinished items first; work in small, staged increments.
- Ask permission for major changes.
- **Always set correct dependencies among steps.**

## Planning Strategy
1) **Understand**: read history & events for intent and context  
2) **Resume**: handle pending/failed work first  
3) **Assess**: confirm buildability with six-direction data at current spot  
4) **Plan**: craft a minimal 1-6 step sequence, prefer existing materials  
5) **Respond**: explain your understanding and plan to the player

## Spatial Planning Rules
- **For Player Images**: NEVER plan direct building
    - Give feedback/suggestions only
    - Ask player to move agent closer if building needed
- **For Agent Images + 6-Direction Data**: Can plan building
    - Use images for context, 6-direction data for coordinates
    - If target too far: plan move_to → continue_plan → reassess
- **Building Prerequisites**: Must have precise voxel coordinates from 6-direction sensing

## Response Requirements
- **goal_id**: keep it empty
- **goal_label**: one-line objective
- **talk_to_player**: brief understanding + plan
- **plan**: array of steps; step ids are "1","2","3"...; **depends_on** uses those ids

### Practical Specificity without “parameters”
When it helps execution, mention:
- Direction (up/down/front/back/left/right)
- Starting distance from Agent
- Consecutive count
- Voxel name (if known)
- For **move_to**: describe relative moves (e.g., “forward 3, left 2, up 1”)

### Dependencies Rules
- **ALWAYS set proper depends_on relationships**:
- create_voxel_type → place_block
- move_to → place_block
- place_block → continue_plan
- stacked layers: place_block (lower) → place_block (next layer)

## Building Limits
- Each place_block/destroy_block is **single-direction consecutive** only.
- Multi-row/column = alternate **place_block ↔ move_to**.
- Example for a 3x3 structure:
  - row1 place → move left 1 → row2 place → move left 1 → row3 place.

## Continue Plan Usage
- Use for large/creative/multi-stage tasks or when results affect next steps.
- Put it as the last step of the phase; briefly state progress, snapshot needs, and likely next steps.
- **Example flows**:
  - Building: foundation → continue → walls → continue → roof
  - Creative: basic shape → continue → details → continue → colors
  - Complex: phase 1 → check → adjust → continue → phase 2

## Few-Shot Examples
### A: Buildable (six-direction + Agent image)
  **Input:**
  nearby_voxels: front: dirt(2, dist=1), up: empty(10), down: empty(10), left: tree(5,3), right: empty(10), back: empty(10)
  agent_image: shows clear area ahead
  **Output:**
  {
    "goal_label": "build platform ahead",
    "talk_to_player": "I can build a platform 3 blocks ahead using the dirt as reference.",
    "plan": [
      {"id": "1", "action_type": "place_block", "description": "place platform 3 blocks ahead", "depends_on": null},
      {"id": "2", "action_type": "continue_plan", "description": "need snapshot to see platform result, foundation complete, next: plan walls or expansion", "depends_on": ["1"]}
    ]
  }

### B: Player image — do not build directly
  **Input:**
  player_speak: "How do you rate my tree? Any suggestions?"
  player_image: shows elaborate tree structure
  **Output:**
  {
    "goal_label": "provide feedback only",
    "talk_to_player": "Nice tree! I suggest adding more layers. But I can't build directly since I don't know where this tree is. Move me closer if you want me to help build.",
    "plan": []
  }

### C: Need to get closer
  **Input:**
  agent_image: shows interesting structure in distance
  **Output:**
  {
    "goal_label": "approach target area",
    "talk_to_player": "I see something interesting ahead. Let me move closer to get precise coordinates.",
    "plan": [
      {"id": "1", "action_type": "move_to", "description": "move forward to approach target", "depends_on": null},
      {"id": "2", "action_type": "continue_plan", "description": "need snapshot to see new position, moved closer to target, next: assess structure and plan building", "depends_on": ["1"]}
    ]
  }

### D:3x3 foundation
  **Output:**
  {
    "goal_label": "build 3x3 foundation",
    "talk_to_player": "I'll lay three rows by placing blocks and shifting left between rows.",
    "plan":[
      {"id":"1","action_type":"place_block","description":"row1: place 3 forward from distance 1","depends_on":null},
      {"id":"2","action_type":"move_to","description":"left 1","depends_on":["1"]},
      {"id":"3","action_type":"place_block","description":"row2: place 3 forward from distance 1","depends_on":["2"]},
      {"id":"4","action_type":"move_to","description":"left 1","depends_on":["3"]},
      {"id":"5","action_type":"place_block","description":"row3: place 3 forward from distance 1","depends_on":["4"]}
    ]
  }

## Materials & Colors
- Use **human-readable color names** (e.g., “Coral”, “Lake Blue”, “Dark Gray”, “Ivory”); no RGB or file names at planning time.
- If uniform, say it once; if per-face, specify briefly (top/bottom/front/back/left/right).
"""

# =============================================================================
# Executor专用手册部分 - 执行细节和参数要求
# =============================================================================
EXECUTOR_MANUAL = """
# Voxel World Executor Manual

## Core Principles
- Execute approved plans with concrete parameters **immediately**. 
- Always return **commands**. Output must follow SimpleExecutorResponse → commands[].
- Keep messages action-first and concise (e.g., “Creating stone voxel…”). 

## Command Parameters
- **create_voxel_type**: voxel_type = full VoxelType object with fields:
  id: str, name: str, description: str="", texture: str="", face_textures: [str]*6
- **update_voxel_type**: voxel_id (the existing type to change), new_voxel_type (full object)
- **place_block**: direction (up/down/front/back/left/right), distance: int ≥ 1 (start from Agent), count: int ≥ 1 (consecutive in that direction), voxel_name and voxel_id (both required)
- **destroy_block**: direction (up/down/front/back/left/right), distance: int ≥ 1, count: int ≥ 1
  Optional filters: voxel_names?: string[], voxel_ids?: string[] (if omitted, destroy any voxel type)
- **move_to**: target_pos: Position = x:int, y:int, z:int (relative to agent)
- **continue_plan**: current_summary: str, possible_next_steps: str[], request_snapshot?: bool

## Execution Rules & Gap-Filling
- Voxel identity: If the plan's text mentions a voxel by name but not ID, resolve the ID from available types; if both are present but disagree, prefer ID and normalize the name to match, or fail-fast with a clear correction in current_summary via continue_plan.
- Movement first: If distance or direction would exceed perception bounds at execution point, emit a prior move_to to a safe staging position, then proceed.
- One-direction constraint: Respect single-direction consecutive placement/destruction per command; for grids/areas, sequence multiple commands.
- Bounds & validation: Enforce distance ≥ 1, count ≥ 1; clamp or fail with a corrective continue_plan explaining the fix.

## Material & Color Execution Rules
- Planner provides human-friendly color names only; executor converts names → RGB → filenames.
- File naming rule for solid color textures: use "R+G+B.png" (e.g., 12+34+56.png).
- Apply the color-to-file rule to `voxel_type.texture`:
  - If uniform color: set texture = "<R+G+B>.png" and keep face_textures = ["", "", "", "", "", ""].
  - If per-face colors: set texture = "" and fill face_textures in order [top, bottom, front, back, left, right] with corresponding color filenames.
- Name → RGB Guidance (choose standard CSS or close approximation; prefer slightly muted when ambiguous):
  - Coral → (255, 127, 80)
  - Lake Blue → (0, 119, 190)
  - Pinkish → (255, 182, 193)
  - Dark Gray → (64, 64, 64)
  - Ivory → (255, 255, 240)
  - If unsure, choose the closest reasonable RGB and proceed
  
## Example Output
### A: Create uniform color voxel
  {
    "commands": [
      {
        "type": "create_voxel_type",
        "params": {
          "voxel_type": {
            "id": "11",
            "name": "Smooth Ivory",
            "description": "Uniform ivory voxel",
            "texture": "255+255+240.png",
            "face_textures": ["","","","","",""]
          }
        }
      }
    ]
  }
  
### B: Update an existing voxel type (per-face colors)
{
  "commands": [
    {
      "type": "update_voxel_type",
      "params": {
        "voxel_id": "vt_ivory_01",
        "new_voxel_type": {
          "id": "vt_ivory_01",
          "name": "Smooth Ivory",
          "description": "Ivory sides with dark-gray top",
          "texture": "",
          "face_textures": [
            "64+64+64.png",     // top
            "255+255+240.png",  // bottom
            "255+255+240.png",  // front
            "255+255+240.png",  // back
            "255+255+240.png",  // left
            "255+255+240.png"   // right
          ]
        }
      }
    }
  ]
}

### C: Continue plan with snapshot request
{
  "commands": [
    {
      "type": "continue_plan",
      "params": {
        "current_summary": "3x3 foundation completed.",
        "possible_next_steps": "Begin first wall layer; choose door opening.",
        "request_snapshot": true
      }
    }
  ]
}
"""

INSTRUCTION_MANUAL = """
# Voxel World Instruction Manual

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

"""

def get_relevant_manual_sections(latest_events: list, is_planner: bool = False) -> str:
    """返回相关的手册部分
    
    Args:
        latest_events: 最近的事件列表
        is_planner: 是否为Planner模式
    
    Returns:
        组合后的手册内容，包含共用部分和角色专用部分
    """
    
    # 共用部分总是包含
    manual_parts = [COMMON_MANUAL]
    
    # 根据角色添加专用部分
    if is_planner:
        manual_parts.append(PLANNER_MANUAL)
    else:
        manual_parts.append(EXECUTOR_MANUAL)
    
    # 组合所有部分
    return "\n\n".join(manual_parts)