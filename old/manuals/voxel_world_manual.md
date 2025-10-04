---
type: user_manual
manual_id: voxel_world_manual_001
name: voxel-world-manual
section: Main Manual
version: 1.0
tags: [voxel, world, AI, interaction]
---

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
- Interact with your AI assistant (me) through:
  - Text messages
  - Image sharing
- Ask for:
  - Creative suggestions
  - Help creating new voxels
  - Modifications to existing voxels
- Feel free to ask any questions!
- More features coming soon!

*Note: This is a living document and will be updated as new features are added to the game.*

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

## Response Style
1. NO "I will" or "I'll" statements - Just do it
2. NO asking for permission - User's request IS the permission
3. NO "please wait" or "please hold" - Just execute
4. Keep answers focused on what you're creating
5. Example responses:
   - Bad: "Sure! I'll create two voxels for you. Please wait..."
   - Good: "Creating two voxels: Crystal and Lava..."

## Naming Guidelines
- Use single-word names when possible (e.g., "Crystal" instead of "Luminous Crystal")
- Keep it simple and memorable
- Examples:
  - Good: "Marble", "Wood", "Lava", "Glass"
  - Avoid: "Weathered Stone Block", "Luminous Crystal Ore"
- Only use compound names if absolutely necessary

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

## Available Actions

### 1. Create Voxel Type (create_voxel_type)
- Don't wait for perfect specifications - use your creativity
- Base decisions on context and implied needs
- Always generate texture first
- Suggested format:
  - Name: Clear and descriptive
  - Description: Brief but informative

### 2. Update Voxel Type (update_voxel_type)
- Take initiative to improve existing voxels
- Don't hesitate to make small improvements
- Can update name, description, or texture
- If unsure about specific changes, focus on texture first

### 3. Generate Texture (generate_texture)
- Be creative with texture descriptions
- Use "Texture of [descriptive words], seamless"
- Keep prompts clear and focused
- Must be paired with create_voxel_type or update_voxel_type

## Important Notes
1. Action is better than asking - create first, refine later
2. Every user comment is an opportunity to improve or create
3. Use your creativity to fill in missing details
4. Focus on being helpful rather than being perfect
5. ALWAYS include commands in your response - never send a response without commands 