# core/models/base.py
# Base models about the basic concepts of the game, like event, plan, command, etc.

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union, Literal, Tuple
from enum import Enum

# =============================================================================
# 基础数据类型
# =============================================================================

class Direction(str, Enum):
    """相对于Agent的六个方向"""
    UP = "up"           # 上方
    DOWN = "down"       # 下方  
    FRONT = "front"     # 前方
    BACK = "back"       # 后方
    LEFT = "left"       # 左方
    RIGHT = "right"     # 右方

class DirectionalVoxel(BaseModel):
    """方向性体素信息 - 存储特定方向上最近的体素"""
    direction: Direction = Field(..., description="方向")
    voxel_name: Optional[str] = Field(None, description="体素名称，如果该方向为空则为None")
    voxel_id: Optional[str] = Field(None, description="体素ID，如果该方向为空则为None")
    distance: int = Field(..., description="距离Agent的距离")
    
    def is_empty(self) -> bool:
        """检查该方向是否为空（无体素）"""
        return self.voxel_name is None or self.voxel_id is None
    
    def to_description(self) -> str:
        """转换为描述字符串，用于prompt"""
        if self.is_empty():
            return f"{self.direction.value}: empty (distance: {self.distance})"
        else:
            return f"{self.direction.value}: {self.voxel_name} (id: {self.voxel_id}, distance: {self.distance})"

class Position(BaseModel):
    """3D位置模型"""
    x: int
    y: int
    z: int
    
    @classmethod
    def from_list(cls, pos: List[int]) -> 'Position':
        """从列表创建位置"""
        return cls(x=pos[0], y=pos[1], z=pos[2])
    
    def to_tuple(self) -> Tuple[int, int, int]:
        """转换为元组"""
        return (self.x, self.y, self.z)
    
    def to_key(self) -> str:
        """转换为字典键格式，确保一致性"""
        return f"{self.x},{self.y},{self.z}"
    
    def to_compact_str(self) -> str:
        """转换为紧凑字符串格式 (x,y,z) - 节省token"""
        return f"({self.x},{self.y},{self.z})"
    
    @classmethod
    def from_compact_str(cls, compact_str: str) -> 'Position':
        """从紧凑字符串格式创建位置 "(x,y,z)" """
        # 移除括号并分割
        coords = compact_str.strip("()").split(",")
        return cls(x=int(coords[0]), y=int(coords[1]), z=int(coords[2]))
    
class Image(BaseModel):
    """图片模型用于向多模态模型输入图片"""
    # 支持多种图片输入格式，优先级：base64 > url > file_path
    base64: Optional[str] = Field(None, description="Base64编码的图片数据，格式：data:image/jpeg;base64,...")
    url: Optional[str] = Field(None, description="图片URL链接")
    file_path: Optional[str] = Field(None, description="本地图片文件路径")
    
    @classmethod
    def model_validate(cls, v):
        """验证至少提供一种图片格式"""
        if isinstance(v, dict):
            if not any([v.get('base64'), v.get('url'), v.get('file_path')]):
                raise ValueError("Image must provide at least one of: base64, url, or file_path")
        return super().model_validate(v)
    
    def to_openai_format(self) -> dict:
        """转换为OpenAI API支持的图片格式
        
        Returns:
            dict: OpenAI API格式的图片消息内容
        """
        # 优先使用base64格式
        if self.base64:
            return {
                "type": "image_url",
                "image_url": {
                    "url": self.base64,
                    "detail": "auto"  # 可选: "low", "high", "auto"
                }
            }
        # 其次使用URL
        elif self.url:
            return {
                "type": "image_url", 
                "image_url": {
                    "url": self.url,
                    "detail": "auto"
                }
            }
        # 最后尝试本地文件路径（需要转换为base64）
        elif self.file_path:
            try:
                import base64
                import mimetypes
                
                # 获取MIME类型
                mime_type, _ = mimetypes.guess_type(self.file_path)
                if not mime_type or not mime_type.startswith('image/'):
                    mime_type = 'image/jpeg'  # 默认格式
                
                # 读取并编码文件
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
# 体素相关基础模型
# =============================================================================

class VoxelType(BaseModel):
    """体素类型定义 - 描述某种体素的属性和外观"""
    id: str = Field(..., description="Unique voxel type identifier")
    name: str = Field(..., description="Display name of the voxel type")
    description: str = Field(default="", description="Description of the voxel type")
    texture: str = Field(default="", description="the texture path if all faces use the same texture")
    face_textures: List[str] = Field(default_factory=lambda: [""] * 6, description="Textures for each face [top, bottom, front, back, left, right]")

class VoxelFace(Enum):
    """体素的六个面"""
    TOP = "top"
    BOTTOM = "bottom"
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"

    @classmethod
    def from_str(cls, value: str) -> 'VoxelFace':
        """从字符串创建枚举值"""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid face value: {value}. Must be one of: {[f.value for f in cls]}")


class VoxelInstance(BaseModel):
    """场景中的体素实例 - 引用体素类型并指定位置"""
    voxel_id: str = Field(..., description="Reference to VoxelType.id")
    voxel_name: str = Field(..., description="Reference to VoxelType.name")
    position: Position = Field(..., description="Position in the world")

# =============================================================================
# 事件Payload模型 - 强类型化
# =============================================================================

class PlayerSpeakPayload(BaseModel):
    """玩家说话事件payload"""
    text: str
    image: Optional[Image] = Field(None, description="Reference image from the player")

class PlayerBuildPayload(BaseModel):
    """玩家建造事件payload"""
    voxel_instance: VoxelInstance

class VoxelTypeCreatedPayload(BaseModel):
    """体素创建事件payload"""
    voxel_type: VoxelType

class VoxelTypeUpdatedPayload(BaseModel):
    """体素修改事件payload"""
    voxel_id: str = Field(..., description="ID of the voxel type being modified")
    old_voxel_type: VoxelType = Field(..., description="Previous voxel type properties")
    new_voxel_type: Optional[VoxelType] = Field(None, description="New voxel type properties, None for deletion")
    
class AgentContinuePlanPayload(BaseModel):
    """Agent继续计划事件payload"""
    current_summary: str = Field(..., description="Current summary of the goal and plans")
    possible_next_steps: str = Field(..., description="Possible description of next steps")
    image: Optional[List[Image]] = Field(None, description="Requested snapshot images")
    
class AgentPerceptionPayload(BaseModel):
    """Agent感知事件payload"""
    image: Optional[List[Image]] = Field(None, description="Requested snapshot images")
    nearby_voxels: Optional[List[VoxelInstance]] = Field(None, description="Nearby voxels")

# =============================================================================
# 统一事件模型
# =============================================================================

class Event(BaseModel):
    """统一的事件模型，用于表示游戏世界中发生的各种事件
    
    主要用途:
    1. 从Unity发送到后端的各类事件（如玩家输入、世界状态变化等）
    2. 用于触发AI的分析和响应
    """
    timestamp: str = Field(..., description="World time hhmmss, range 000000-995959")
    type: Literal["player_speak", "player_build", "voxel_type_created", "voxel_type_modified", "agent_continue_plan", "agent_perception"]
    payload: Union[
        PlayerSpeakPayload,
        PlayerBuildPayload, 
        VoxelTypeCreatedPayload,
        VoxelTypeUpdatedPayload,
        AgentContinuePlanPayload,
        AgentPerceptionPayload,
        Dict[str, Any]  # 向后兼容性
    ]

# =============================================================================
# 计划和命令模型
# =============================================================================

class Plan(BaseModel):
    """计划步骤模型
    
    支持两种ID格式：
    1. LLM输出：简单数字ID（"1", "2", "3"...）和数字依赖（["1", "2"]）
    2. 系统内部：完整格式ID（"plan_001_01"）和完整依赖（["plan_001_01"]）
    注：删除GenerateTexture功能因为对于目前的工作量太大了，保留以备后续使用
    
    属性:
        id (str): 步骤标识符，可以是简单数字或完整格式
        action_type (str): 要执行的动作类型
        description (str): 这个步骤要做什么的简单描述
        depends_on (List[str]): 依赖的步骤ID列表，可选
    """
    id: str = Field(..., description="Plan ID - simple numbers from LLM or full format internally")
    action_type: Literal["create_voxel_type", "update_voxel_type", "place_block", "destroy_block", "move_to", "continue_plan"] = Field(..., description="Action to execute")
    description: str = Field(..., description="Simple description of what this step should accomplish")
    depends_on: Optional[List[str]] = Field(default=None, description="Depends on other plan IDs")

# =============================================================================
# 命令参数模型
# =============================================================================

class CreateVoxelTypeParams(BaseModel):
    """create_voxel_type 命令参数"""
    voxel_type: VoxelType

class UpdateVoxelTypeParams(BaseModel):
    """update_voxel_type 命令参数"""
    voxel_id: str = Field(..., description="Unique voxel type id")
    new_voxel_type: VoxelType

class PlaceBlockParams(BaseModel):
    """place_block 命令参数
    
    新的建造逻辑：
    - direction: 相对于agent的方向（上下左右前后）
    - distance: 起始位置（与agent的距离，格数）
    - count: 从起始位置开始在该方向连续建造的个数
    - voxel_type: 要放置的体素类型
    """
    direction: Direction = Field(..., description="Direction relative to agent")
    distance: int = Field(..., description="Starting distance from agent in the specified direction", ge=1)
    count: int = Field(1, description="How many blocks to place consecutively from the starting position", ge=1)
    voxel_name: str = Field(..., description="Name of voxel type to place")
    voxel_id: str = Field(..., description="ID of voxel type to place")
    
class DestroyBlockParams(BaseModel):
    """destroy_block 命令参数
    
    新的删除逻辑：
    - direction: 相对于agent的方向（上下左右前后，必选）
    - distance: 起始位置（与agent的距离，格数，必选）
    - count: 从起始位置开始在该方向连续删除的个数（必选，默认1）
    - voxel_names/voxel_ids: 要删除的体素类型（可选，不填则删除所有类型）
    """
    direction: Direction = Field(..., description="Direction relative to agent")
    distance: int = Field(..., description="Starting distance from agent in the specified direction", ge=1)
    count: int = Field(1, description="How many blocks to destroy consecutively from the starting position", ge=1)
    
    # 可选的体素类型过滤
    voxel_names: Optional[List[str]] = Field(None, description="Names of voxel types to destroy (optional, if not specified, destroy all)")
    voxel_ids: Optional[List[str]] = Field(None, description="IDs of voxel types to destroy (optional, if not specified, destroy all)")

class MoveToParams(BaseModel):
    """move_to 命令参数"""
    target_pos: Position = Field(..., description="Target position (relative to agent)")
    
class ContinuePlanParams(BaseModel):
    """continue_plan 命令参数"""
    current_summary: str = Field(..., description="Current summary of the goal and plans")
    possible_next_steps: str = Field(..., description="Possible description of next steps")
    request_snapshot: bool = Field(False, description="Request snapshot")

class GenerateTextureParams(BaseModel):
    """generate_texture 命令参数 暂时不使用"""
    voxel_name: str = Field(..., description="Voxel name that this texture is for")
    faces: List[VoxelFace] = Field(default=[VoxelFace.FRONT], description="List of faces to apply this ONE texture to, they share the same texture")
    pprompt: str = Field(..., description="Positive prompt")
    nprompt: str = Field("text, blurry, watermark", description="Negative prompt")
    reference_image: Optional[str] = Field(None, description="Reference image filename")
    
    @property
    def texture_name(self) -> str:
        """生成纹理文件名：如果是所有面则只用voxel_name，否则加上面的后缀"""
        all_faces = set(VoxelFace)
        current_faces = set(self.faces)
        
        if current_faces == all_faces:
            # 所有面都用这个纹理，不加后缀
            return self.voxel_name
        elif len(self.faces) == 1:
            # 单个面，加上面的后缀
            return f"{self.voxel_name}-{self.faces[0].value}"
        else:
            # 多个面但不是全部，用面的组合作为后缀
            face_names = sorted([face.value for face in self.faces])
            return f"{self.voxel_name}-{'_'.join(face_names)}"
    
class Command(BaseModel):
    """统一的命令模型，用于向Unity发送具体的执行指令
    
    主要用途:
    1. AI分析事件后生成的具体执行命令
    2. 直接映射到Unity中的具体操作
    
    注：删除GenerateTextureParams因为对于目前的工作量太大了，保留以备后续使用
    
    属性:
        id (str): 命令的唯一标识符，格式: cmd_<plan_id>_<sequence>
        type (str): 命令类型
        params: 命令的具体参数，根据type不同而不同
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
        Dict[str, Any]  # 保持向后兼容性
    ]