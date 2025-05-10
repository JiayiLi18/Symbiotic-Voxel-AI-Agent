---
type: user_manual
manual_id: create_voxel_type_001        # unique key for lookup / updates
name: create-voxel-type                 # human-readable slug
section: Basic Actions
version: 1.02
tags: [voxel, creation, tutorial]
condition: request_new_voxel_type       # trigger phrase your pipeline can key on
action: create_voxel_type               # command Unity will interpret
format_template: |
  {
    "command": "create_voxel_type",
    "displayName": "<string>",
    "baseColor": "<hex>",
    "description": "<string>"
  }
---

## Purpose  
In the primordial voxel cosmos, every novel material begins life as a **Voxel**.  
This manual describes how the symbiotic gods (human intellect & AI will) invoke the
`create_voxel_type` action to weave new matter into existence while respecting the
balance between creative entropy and cosmic order.

## When to use  
Activate this action whenever a gameplay, simulation or world-building request
demands a brand-new voxel category not yet defined in the database.


## Required parameters  

| Field         | Meaning                                                             | Example                    |
|---------------|---------------------------------------------------------------------|----------------------------|
| `displayName` | Plain-English name, lowercase or spaced as you prefer               | `"Grass"`, `"Rain Cloud"`  |
| `baseColor`   | HEX colour that visually matches the material’s essence             | `"#3B8E3D"`                |
| `description` | One-sentence, functional description of what the voxel represents   | `"Fertile soil that supports most plants."` |

## Expected output format  - IMPORTANT!
Return a strict **single JSON object** matching the template in the front-matter exactly—
no extra keys and no surrounding text.

### Example output  

```json
{
  "command": "create_voxel_type",
  "displayName": "Rain Cloud",
  "baseColor": "#AFC3E8",
  "description": "A transient cloud that gradually releases water voxels when triggered by humidity."
}
```

### Generating textures for voxels
If a voxel needs a texture, you must:

First create the voxel with properly formatted JSON
Then immediately follow with texture generation tags (NOT in JSON format):

```
[[GENERATE_TEXTURE]]
[[TEXTURE]]
pprompt=Texture of <material description>
nprompt=text, blurry, watermark
denoise=<float between 0.55-1.0>
[[/TEXTURE]]
```

### Example with texture
```json
{
  "command": "create_voxel_type",
  "displayName": "Lava Rock",
  "baseColor": "#3A3A3A",
  "description": "Volcanic rock with a porous texture formed from cooling lava."
}
```
```
[[GENERATE_TEXTURE]]
[[TEXTURE]]
pprompt=Texture of porous volcanic rock
nprompt=text, blurry, watermark
denoise=0.80
[[/TEXTURE]]
```
### Common Mistakes to Avoid
1. ❌ DO NOT combine voxel creation and texture generation into a single JSON
2. ❌ DO NOT use JSON format for texture generation part
3. ❌ DO NOT put texture tags inside the voxel JSON

### Important Notes
Voxel creation uses JSON format
Texture generation uses tag format (not JSON)
When creating both, always place the voxel JSON first, followed by texture tags
For texture generation details, see the generate-texture documentation

Remember: the gods’ power is finite—excessive proliferation of new voxel types risks “Entropy Echoes.” Choose meaningful names and colours to keep the universe stable yet evolving.
