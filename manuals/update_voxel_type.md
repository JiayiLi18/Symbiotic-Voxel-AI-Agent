---
type: user_manual
manual_id: update_voxel_type_001
name: update-voxel-type
section: Basic Actions
version: 1.0
tags: [voxel, update, modification]
condition: request_voxel_update
action: update_voxel_type
format_template: "Update voxel '{name}' with new properties"
---

## Purpose
Modify existing voxel types to update their properties, textures, or behaviors while maintaining game balance and consistency.

## Important Note
When updating a voxel's texture, you MUST first generate the new texture using the generate_texture command. The texture path from that command will be used in the voxel update process.

## Update Guidelines

1. **Texture Updates**
   - Always generate new texture first using generate_texture command
   - Consider the voxel's role and theme when designing new textures
   - Ensure visual consistency with related voxels
   - Example: "Can you change my stone voxel to add a texture to it?"
   - Response should:
     1. Generate new texture with appropriate parameters
     2. Use update_voxel_type command with the new texture path

2. **Property Updates**
   - Update description to reflect new characteristics
   - Modify transparency settings if needed
   - Maintain logical consistency with voxel's purpose
   - Example: "Make my glass voxel more transparent"

3. **Name Recognition**
   - Use exact voxel name for updates
   - Confirm voxel existence before updating
   - Handle common variations (e.g., "stone" vs "stone block")

## Update Process
1. Identify target voxel by name
2. Generate new texture if needed
3. Specify update parameters
4. Apply updates while maintaining consistency

## When to Update
- When users request texture changes
- When improving visual quality
- When adjusting voxel properties
- When enhancing existing voxels

## Response Format
For texture updates:
1. First use generate_texture command
2. Then use update_voxel_type command with:
   - name: exact voxel name
   - texture: path from generate_texture
   - other properties as needed

## Common Update Scenarios

1. **Texture Enhancement**
   ```
   User: "Can you change my stone voxel to add a texture to it?"
   Response: 
   1. Generate new stone texture
   2. Update stone voxel with new texture
   ```

2. **Property Modification**
   ```
   User: "Make my glass voxel more transparent"
   Response:
   1. Update glass voxel with is_transparent=true
   ```

Remember: Always maintain the voxel's core purpose while enhancing its features. 