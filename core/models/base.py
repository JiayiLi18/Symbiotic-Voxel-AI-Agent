# core/models/base.py
# Base models about the basic concepts of the game, like event, plan, command, etc.

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union, Literal, Tuple
from enum import Enum

# =============================================================================
# Basic Data Types
# =============================================================================

class Direction(str, Enum):
    """Six directions relative to Agent"""
    UP = "up"           # Up
    DOWN = "down"       # Down  
    FRONT = "front"     # Front
    BACK = "back"       # Back
    LEFT = "left"       # Left
    RIGHT = "right"     # Right

class DirectionalVoxel(BaseModel):
    """Directional voxel information - stores the nearest voxel in a specific direction"""
    direction: Direction = Field(..., description="The direction of the voxel relative to the agent. One of: up, down, left, right, front, back (relative to agent facing).")
    voxel_name: Optional[str] = Field(None, description="Voxel name, None if the direction is empty")
    voxel_id: Optional[str] = Field(None, description="Voxel ID, must match voxel_name (ID-Name pair is 1:1).")
    distance: int = Field(..., description="Distance from Agent. 1 = adjacent; 2+ = with gap.")
    
    def is_empty(self) -> bool:
        """Check if this direction is empty (no voxel)"""
        return self.voxel_name is None or self.voxel_id is None
    
    def to_description(self) -> str:
        """Convert to description string for prompt"""
        if self.is_empty():
            return f"{self.direction.value}: empty (distance: {self.distance})"
        else:
            return f"{self.direction.value}: {self.voxel_name} (id: {self.voxel_id}, distance: {self.distance})"

class Position(BaseModel):
    """3D position model"""
    x: int
    y: int
    z: int
    
    @classmethod
    def from_list(cls, pos: List[int]) -> 'Position':
        """Create position from list"""
        return cls(x=pos[0], y=pos[1], z=pos[2])
    
    def to_tuple(self) -> Tuple[int, int, int]:
        """Convert to tuple"""
        return (self.x, self.y, self.z)
    
    def to_key(self) -> str:
        """Convert to dictionary key format, ensuring consistency"""
        return f"{self.x},{self.y},{self.z}"
    
    def to_compact_str(self) -> str:
        """Convert to compact string format (x,y,z) - saves tokens"""
        return f"({self.x},{self.y},{self.z})"
    
    @classmethod
    def from_compact_str(cls, compact_str: str) -> 'Position':
        """Create position from compact string format "(x,y,z)" """
        # Remove brackets and split
        coords = compact_str.strip("()").split(",")
        return cls(x=int(coords[0]), y=int(coords[1]), z=int(coords[2]))
    
class Image(BaseModel):
    """Image model for inputting images to multimodal models"""
    # Support multiple image input formats, priority: base64 > url > file_path
    base64: Optional[str] = Field(None, description="Base64 encoded image data, format: data:image/jpeg;base64,...")
    url: Optional[str] = Field(None, description="Image URL link")
    file_path: Optional[str] = Field(None, description="Local image file path")
    
    @classmethod
    def model_validate(cls, v):
        """Validate that at least one image format is provided"""
        if isinstance(v, dict):
            # 将空字符串视为None，避免验证失败
            base64_val = v.get('base64') or None
            url_val = v.get('url') or None
            file_path_val = v.get('file_path') or None
            
            # 移除空字符串
            if base64_val == "":
                base64_val = None
            if url_val == "":
                url_val = None
            if file_path_val == "":
                file_path_val = None
            
            if not any([base64_val, url_val, file_path_val]):
                raise ValueError("Image must provide at least one of: base64, url, or file_path")
        return super().model_validate(v)
    
    def to_openai_format(self) -> dict:
        """Convert to OpenAI API supported image format
        
        Returns:
            dict: OpenAI API format image message content
        """
        # Prefer base64 format
        if self.base64:
            base64_data = self.base64
            
            # Check if base64 already has data URI prefix (data:image/...;base64,)
            if not base64_data.startswith('data:image/'):
                # If not, detect MIME type from base64 data or use default
                # Try to detect if it's PNG (starts with iVBOR) or JPEG (starts with /9j/)
                mime_type = 'image/jpeg'  # Default
                if base64_data.startswith('iVBOR'):
                    mime_type = 'image/png'
                elif base64_data.startswith('/9j/'):
                    mime_type = 'image/jpeg'
                elif base64_data.startswith('R0lGOD'):
                    mime_type = 'image/gif'
                elif base64_data.startswith('UklGR'):
                    mime_type = 'image/webp'
                
                # Add data URI prefix if missing
                base64_data = f"data:{mime_type};base64,{base64_data}"
            # If it already has prefix but missing the comma separator, add it
            elif ';base64,' not in base64_data and base64_data.startswith('data:image/'):
                # Extract MIME type and base64 content
                if ';base64' in base64_data:
                    parts = base64_data.split(';base64')
                    mime_type = parts[0].replace('data:', '')
                    base64_content = parts[1] if len(parts) > 1 else ''
                    base64_data = f"data:{mime_type};base64,{base64_content}"
            
            return {
                "type": "image_url",
                "image_url": {
                    "url": base64_data,
                    "detail": "auto"  # 可选: "low", "high", "auto"
                }
            }
        # Then use URL
        elif self.url:
            return {
                "type": "image_url", 
                "image_url": {
                    "url": self.url,
                    "detail": "auto"
                }
            }
        # Finally try local file path (needs to be converted to base64)
        elif self.file_path:
            try:
                import base64
                import mimetypes
                
                # Get MIME type
                mime_type, _ = mimetypes.guess_type(self.file_path)
                if not mime_type or not mime_type.startswith('image/'):
                    mime_type = 'image/jpeg'  # Default format
                
                # Read and encode file
                with open(self.file_path, 'rb') as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')
                
                return {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{encoded}",
                        "detail": "auto"
                    }
                }
            except Exception as e:
                raise ValueError(f"Failed to process image file {self.file_path}: {str(e)}")
        
        raise ValueError("No valid image data provided")

# =============================================================================
# Voxel-related Base Models
# =============================================================================

class VoxelType(BaseModel):
    """Voxel type definition - describes the properties and appearance of a voxel type"""
    id: str = Field(..., description="Unique voxel type identifier")
    name: str = Field(..., description="Display name of the voxel type")
    description: str = Field(default="", description="Optional description of the voxel type")
    face_textures: List[str] = Field(default_factory=lambda: [""] * 6, description="Textures for each face in order: [+x(right), -x(left), +y(top), -y(bottom), +z(front), -z(back)]")

class VoxelFace(Enum):
    """Six faces of a voxel"""
    TOP = "top"
    BOTTOM = "bottom"
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"

    @classmethod
    def from_str(cls, value: str) -> 'VoxelFace':
        """Create enum value from string"""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid face value: {value}. Must be one of: {[f.value for f in cls]}")


class VoxelInstance(BaseModel):
    """Voxel instance in scene - references voxel type and specifies position"""
    voxel_id: str = Field(..., description="Reference to VoxelType.id")
    voxel_name: str = Field(..., description="Reference to VoxelType.name")
    position: Position = Field(..., description="Position in the world")

# =============================================================================
# Event Payload Models - Strongly Typed
# =============================================================================

class PlayerSpeakPayload(BaseModel):
    """Player speak event payload"""
    text: str
    image: Optional[Image] = Field(None, description="Reference image from the player")

class PlayerBuildPayload(BaseModel):
    """Player build event payload - can handle multiple voxel operations (place/delete)"""
    voxel_instances: List[VoxelInstance] = Field(..., description="List of voxel instances to place or delete. For deletion: voxel_id='0' and voxel_name='air'")

class VoxelTypeCreatedPayload(BaseModel):
    """Voxel type created event payload"""
    voxel_type: VoxelType

class VoxelTypeUpdatedPayload(BaseModel):
    """Voxel type updated event payload"""
    voxel_id: str = Field(..., description="ID of the voxel type being modified")
    old_voxel_type: VoxelType = Field(..., description="Previous voxel type properties")
    new_voxel_type: Optional[VoxelType] = Field(None, description="New voxel type properties, None for deletion")
    
class AgentContinuePlanPayload(BaseModel):
    """Agent continue plan event payload"""
    current_summary: str = Field(..., description="Current summary of the goal and plans")
    possible_next_steps: str = Field(..., description="Possible description of next steps")
    image: Optional[List[Image]] = Field(None, description="Requested snapshot images")
    
class AgentPerceptionPayload(BaseModel):
    """Agent perception event payload"""
    image: Optional[List[Image]] = Field(None, description="Requested snapshot images")
# =============================================================================
# Unified Event Model
# =============================================================================

class Event(BaseModel):
    """Unified event model for representing various events occurring in the game world
    
    Main purposes:
    1. Various events sent from Unity to backend (such as player input, world state changes, etc.)
    2. Used to trigger AI analysis and response
    """
    timestamp: str = Field(..., description="World time hhmmss, range 000000-995959")
    type: Literal["player_speak", "player_build", "voxel_type_created", "voxel_type_updated", "agent_continue_plan", "agent_perception"]
    payload: Union[
        PlayerSpeakPayload,
        PlayerBuildPayload, 
        VoxelTypeCreatedPayload,
        VoxelTypeUpdatedPayload,
        AgentContinuePlanPayload,
        AgentPerceptionPayload,
        Dict[str, Any]  # Backward compatibility
    ]

# =============================================================================
# Plan and Command Models
# =============================================================================

class Plan(BaseModel):
    """Plan step model
    
    Supports two ID formats:
    1. LLM output: Simple numeric IDs ("1", "2", "3"...) and numeric dependencies (["1", "2"])
    2. System internal: Full format IDs ("plan_001_01") and full dependencies (["plan_001_01"])
    Note: GenerateTexture functionality removed due to excessive workload, kept for future use
    
    Attributes:
        id (str): Step identifier, can be simple number or full format
        action_type (str): Type of action to execute
        description (str): Simple description of what this step should accomplish
        depends_on (List[str]): List of dependent step IDs, optional
    """
    id: str = Field(..., description="Step ID, simple numbers: '1','2','3'.")
    action_type: Literal["create_voxel_type", "update_voxel_type", "place_block", "destroy_block", "move_to", "continue_plan"] = Field(..., description="Action type for this step.")
    description: str = Field(
        ...,
        description=(
            "1-2 short sentences. "
            "Use compact style, not a paragraph. "
            "Example: 'To build a platform 3 blocks ahead using the dirt as reference.'."
        )
    )
    depends_on: Optional[List[str]] = Field(default=None, description="Optional list of step IDs this step depends on, e.g., ['1','2'].")

# =============================================================================
# Command Parameter Models
# =============================================================================

class CreateVoxelTypeParams(BaseModel):
    """create_voxel_type command parameters"""
    voxel_type: VoxelType = Field(..., description="Complete voxel type object including id, name, description, and exactly 6 face_textures.")

class UpdateVoxelTypeParams(BaseModel):
    """update_voxel_type command parameters"""
    voxel_id: str = Field(..., description="ID of existing voxel type to update (must match an existing ID).")
    new_voxel_type: VoxelType = Field(..., description="Full voxel type definition with modifications applied. ID must remain the same.")

class PlaceBlockParams(BaseModel):
    """place_block command parameters
    
    New building logic:
    - start_offset: Where to place the FIRST block, relative to the agent (e.g. {x:1, y:0, z:1} = right 1, front 1)
    - expand_direction: Direction to build consecutive blocks (if count > 1)
    - count: Number of consecutive blocks to place
    - voxel_type: Voxel type to place
    """
    start_offset: Position = Field(..., description="Starting position relative to agent. Example: {x:1, y:0, z:1}.")
    expand_direction: Direction = Field(Direction.UP, description="Direction to build consecutive blocks (if count > 1). Defaults to UP.")
    count: int = Field(1, ge=1, description="How many consecutive blocks to place in the expand_direction.")
    voxel_name: str = Field(..., description="Voxel name to place. Must match a voxel in voxel_definitions.")
    voxel_id: str = Field(..., description="Voxel ID to place. Must match voxel_name (ID-Name pair is 1:1).")
    
class DestroyBlockParams(BaseModel):
    """destroy_block command parameters
    
    New destruction logic:
    - start_offset: Where to start destroying, relative to the agent
    - expand_direction: Direction to destroy consecutive blocks
    - count: Number of consecutive blocks to destroy
    """
    start_offset: Position = Field(..., description="Starting position relative to agent. Example: {x:1, y:0, z:1}.")
    expand_direction: Direction = Field(Direction.UP, description="Direction to destroy consecutive blocks (if count > 1). Defaults to UP.")
    count: int = Field(1, ge=1, description="How many consecutive blocks to destroy in the expand_direction.")
    
    # 可选的体素类型过滤
    voxel_names: Optional[List[str]] = Field(None, description="Optional filter: destroy only these voxel names. If omitted, destroy all types.")
    voxel_ids: Optional[List[str]] = Field(None, description="Optional filter: destroy only these voxel IDs. If omitted, destroy all types.")

class MoveToParams(BaseModel):
    """move_to command parameters"""
    target_pos: Position = Field(..., description="Target offset relative to agent. Example: {x:1,y:0,z:-3}.")
    
class ContinuePlanParams(BaseModel):
    """continue_plan command parameters"""
    current_summary: str = Field(..., description="Max 2 short lines summarizing current progress.")
    possible_next_steps: str = Field(..., description="Max 2 short lines describing likely next moves.")
    request_snapshot: bool = Field(False, description="True if Loom wants a new snapshot before planning further.")

class GenerateTextureParams(BaseModel):
    """generate_texture command parameters - temporarily unused"""
    voxel_name: str = Field(..., description="Voxel name that this texture is for")
    faces: List[VoxelFace] = Field(default=[VoxelFace.FRONT], description="List of faces to apply this ONE texture to, they share the same texture")
    pprompt: str = Field(..., description="Positive prompt")
    nprompt: str = Field("text, blurry, watermark", description="Negative prompt")
    reference_image: Optional[str] = Field(None, description="Reference image filename")
    
    @property
    def texture_name(self) -> str:
        """Generate texture filename: use only voxel_name if all faces, otherwise add face suffix"""
        all_faces = set(VoxelFace)
        current_faces = set(self.faces)
        
        if current_faces == all_faces:
            # All faces use this texture, no suffix
            return self.voxel_name
        elif len(self.faces) == 1:
            # Single face, add face suffix
            return f"{self.voxel_name}-{self.faces[0].value}"
        else:
            # Multiple faces but not all, use face combination as suffix
            face_names = sorted([face.value for face in self.faces])
            return f"{self.voxel_name}-{'_'.join(face_names)}"
    
class Command(BaseModel):
    """Unified command model for sending specific execution instructions to Unity
    
    Main purposes:
    1. Specific execution commands generated by AI after analyzing events
    2. Direct mapping to specific operations in Unity
    
    Note: GenerateTextureParams removed due to excessive workload, kept for future use
    
    Attributes:
        id (str): Unique command identifier, format: cmd_<plan_id>_<sequence>
        type (str): Command type
        params: Specific parameters for the command, varies by type
    """
    id: str = Field(..., description="Command ID in format: cmd_<plan_id>_<sequence>")
    type: Literal["create_voxel_type", "update_voxel_type", "place_block", "destroy_block", "move_to", "continue_plan"]
    params: Union[
        CreateVoxelTypeParams,
        UpdateVoxelTypeParams, 
        PlaceBlockParams,
        DestroyBlockParams,
        MoveToParams,
        ContinuePlanParams,
        Dict[str, Any]  # Maintain backward compatibility
    ]