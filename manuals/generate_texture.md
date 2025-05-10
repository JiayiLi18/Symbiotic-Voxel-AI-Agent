---
type: user_manual
manual_id: generate_texture_001
name: generate-texture
section: Advanced Actions
version: 1.01
tags: [texture, generation, image]
condition: request_texture_generation
action: generate_texture
format_template: |
  [[GENERATE_TEXTURE]]
  [[TEXTURE]]
  pprompt=Texture of <material description>
  nprompt=<negative prompts>
  denoise=<float between 0.55-1.0>
  [[/TEXTURE]]
---

## Purpose
Generate custom textures for materials and surfaces.

## When to use
- When creating a new voxel type that needs a texture
- When generating a standalone texture without creating a voxel type

## Required Syntax - IMPORTANT!

The texture generation command uses this specific tag-based structure (NOT JSON):

1. `[[GENERATE_TEXTURE]]` marker to indicate texture generation is needed
2. Parameters within `[[TEXTURE]]` and `[[/TEXTURE]]` tags

### Parameters

| Parameter | Description | Format | Constraints |
|-----------|-------------|--------|------------|
| `pprompt` | Positive prompt | String | Must follow "Texture of xxx" pattern; keep concise |
| `nprompt` | Negative prompt | String | Default: "text, blurry, watermark" |
| `denoise` | Similarity control | Float | Range: 0.55-1.0 |

### Denoising Explanation
- **Lower values (0.55-0.7)**: More similar to input image
- **Higher values (0.7-1.0)**: Less similar to input image
- Consider whether similarity to an existing image is needed when setting this value

## Usage Examples

### Example 1: With Voxel Type Creation

First provide the voxel JSON:
```json
{
  "command": "create_voxel_type",
  "displayName": "Marble",
  "baseColor": "#E8E8E0",
  "description": "Polished stone with distinctive veining patterns."
}
```

Then IMMEDIATELY follow with texture tags (NOT in JSON format):
```
[[GENERATE_TEXTURE]]
[[TEXTURE]]
pprompt=Texture of white marble with gray veins
nprompt=text, blurry, watermark
denoise=0.75
[[/TEXTURE]]
```

### Example 2: Standalone Texture Generation

Use only the texture tags:
```
[[GENERATE_TEXTURE]]
[[TEXTURE]]
pprompt=Texture of rough sandstone
nprompt=text, blurry, watermark
denoise=0.85
[[/TEXTURE]]
```

## Common Mistakes to Avoid

1. ❌ DO NOT use JSON format for texture generation:
   ```json
   {
     "command": "generate_texture",
     "texture": {
       "pprompt": "Texture of a vibrant flower",
       "nprompt": "text, blurry, watermark",
       "denoise": 0.85
     }
   }
   ```

2. ❌ DO NOT omit the texture tags when requesting a voxel with texture:
   ```
   [Voxel JSON only with no [[GENERATE_TEXTURE]] tags]
   ```

3. ❌ DO NOT mix the tag format with JSON:
   ```
   [[GENERATE_TEXTURE]]
   {
     "pprompt": "Texture of rough sandstone",
     "nprompt": "text, blurry, watermark",
     "denoise": 0.85
   }
   ```

## Important Notes

1. The texture tag format is separate from and different than the JSON format used for voxel creation
2. When using both voxel creation and texture generation, always provide the voxel JSON first, then the texture tags
3. Each parameter in the texture tags must be on its own line
4. Always include the `[[GENERATE_TEXTURE]]` marker before the `[[TEXTURE]]` tags