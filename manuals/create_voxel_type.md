---
type: user_manual
manual_id: create_voxel_type_001        # unique key for lookup / updates
name: create-voxel-type                 # human-readable slug
section: Basic Actions
version: 1.06
tags: [voxel, creation, tutorial]
condition: request_new_voxel_type       # trigger phrase your pipeline can key on
action: create_voxel_type               # command Unity will interpret
---

## Important Note
Before creating a new voxel type, you MUST first generate its texture using the generate_texture command. The texture path from that command will be used in the voxel creation process.

## Purpose
Create new voxel types that enrich the game world, each bringing its own properties and gameplay possibilities.

## Creative Guidelines

1. **Voxel Identity**
   - Give each voxel a clear purpose and role
   - Consider how it fits into the game's ecosystem
   - Think about its interaction with other voxels

2. **Visual Design**
   - Consider how it looks in different lighting
   - Think about its visual impact in builds
   - Note: Base color is handled by Unity, Python side always uses white (RGB: 255,255,255)

3. **Properties**
   - Define clear physical characteristics
   - Consider environmental interactions
   - Think about potential crafting uses

4. **World Integration**
   - Consider where it naturally occurs
   - Think about its role in player progression
   - Plan potential building applications

## Design Tips

1. **Naming**
   - Use clear, descriptive names
   - Consider material properties in the name
   - Make it memorable and fitting

2. **Description Writing**
   - Be clear and concise
   - Include key properties
   - Mention special behaviors

3. **Texture Considerations**
   - Every voxel needs a matching texture (generate it first!)
   - Consider surface details
   - Think about tiling patterns

4. **Creative Suggestions**
   - Look for gaps in the current voxel ecosystem
   - Consider creating themed sets (e.g., ancient ruins, crystal caves)
   - Think about unique gameplay mechanics
   - Combine existing concepts in novel ways
   - Consider seasonal or special event voxels

Remember: Each new voxel should add meaningful variety to the game world while maintaining balance and purpose.

## When to use  
- When users request new voxel types
- When you identify gaps in the current ecosystem
- When you have creative ideas for enhancing gameplay
- When building themed sets or collections
- When users provide vague requests (use your creativity!)

## Initiative Guidelines
1. **Analyze Current Ecosystem**
   - What categories are underrepresented?
   - What themes could be expanded?
   - What building styles need more options?

2. **Suggest Complete Concepts**
   - Don't just ask for parameters
   - Propose specific ideas with reasoning
   - Consider both aesthetics and functionality

3. **Think in Sets**
   - Consider creating related voxels
   - Build upon existing themes
   - Create coherent collections

4. **Balance Creativity with Utility**
   - Make visually interesting voxels
   - Ensure practical usefulness
   - Consider player progression