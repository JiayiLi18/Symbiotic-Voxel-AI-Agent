import os
import base64
import io
from core.models.protocol import EventBatch, PlanPermission
from core.models.game_state import GameState
from core.models.base import Image
from typing import Optional, List, Union, Any, Dict

# Tool references - imported from main.py
def get_tools():
    """Get tool instances"""
    from api.main import session_manager
    
    return session_manager


async def generate_context_prompt(input_data: Union[EventBatch, PlanPermission], is_planner: Optional[bool] = None) -> str:
    """Generate context prompt
    
    Args:
        input_data: EventBatch (for planner) or PlanPermission (for executor)
        is_planner: Whether this is planner mode. If None, inferred from input_data type.
                   EventBatch -> planner (True), PlanPermission -> executor (False)
    """
    
    # Infer is_planner from input type if not explicitly provided
    if is_planner is None:
        is_planner = isinstance(input_data, EventBatch)
    
    # Process images: if 4 images found, merge them into 1 (before generating context)
    if isinstance(input_data, EventBatch):
        _process_images_in_event_batch(input_data)
    
    # Get tool instances
    session_manager = get_tools()
    
    # Extract basic information
    session_id = input_data.session_id
    game_state = input_data.game_state
    
    context_parts = []
    
    # 1. Add specific information based on input type
    if isinstance(input_data, EventBatch):
        # Planner mode: add event information
        if input_data.events:
            context_parts.append("## Events")
            for event in input_data.events:
                event_desc = f"[{event.timestamp}] {event.type}"
                if hasattr(event.payload, 'text'):
                    event_desc += f": {event.payload.text}"
                elif hasattr(event.payload, 'voxel_instances'):
                    # Handle multiple voxel operations
                    operations = []
                    for voxel in event.payload.voxel_instances:
                        if voxel.voxel_id == "0" and voxel.voxel_name == "air":
                            operations.append(f"deleted at {voxel.position.to_compact_str()}")
                        else:
                            operations.append(f"{voxel.voxel_name} at {voxel.position.to_compact_str()}")
                    event_desc += f": {', '.join(operations)}"
                elif hasattr(event.payload, 'voxel_instance'):
                    # Backward compatibility for single voxel
                    voxel = event.payload.voxel_instance
                    event_desc += f": {voxel.voxel_name} at {voxel.position.to_compact_str()}"
                elif hasattr(event.payload, 'nearby_voxels') and event.payload.nearby_voxels:
                    # Process nearby_voxels, convert to quantity statistics
                    voxel_stats = _process_nearby_voxels_stats(event.payload.nearby_voxels)
                    event_desc += f": {voxel_stats}"
                elif hasattr(event.payload, 'voxel_type'):
                    # voxel_type_created
                    event_desc += f": {event.payload.voxel_type.name}"
                elif hasattr(event.payload, 'voxel_id'):
                    # voxel_type_updated
                    if hasattr(event.payload, 'new_voxel_type') and event.payload.new_voxel_type is None:
                        # Deletion
                        event_desc += f": deleted {event.payload.voxel_id}"
                    elif hasattr(event.payload, 'new_voxel_type'):
                        # Modification
                        event_desc += f": {event.payload.voxel_id} → {event.payload.new_voxel_type.name}"
                    else:
                        event_desc += f": {event.payload.voxel_id}"
                context_parts.append(f"- {event_desc}")
        
    elif isinstance(input_data, PlanPermission):
        # Executor mode: add plan permission information
        context_parts.append("## Plan Permission")
        context_parts.append(f"- Goal: {input_data.goal_label}")
        
        if input_data.approved_plans:
            context_parts.append("### Approved Plans")
            for plan in input_data.approved_plans:
                depends_info = f" (depends on: {plan.depends_on})" if plan.depends_on else ""
                context_parts.append(f"- [{plan.id}] {plan.action_type}: {plan.description}{depends_info}")
        
        if input_data.additional_info:
            context_parts.append("### Additional Information")
            context_parts.append(f"- {input_data.additional_info}")
    else:
        raise ValueError(f"Unsupported input type: {type(input_data)}")
    
    # 2. Add game state information (common logic)
    _add_game_state_section(context_parts, game_state)
    
    # 3. Add history information (only for planner mode)
    if is_planner:
        _add_history_section(context_parts, session_manager, session_id)
    
    # 4. Add goals and progress information
    if game_state:
        _add_goal_status_section(context_parts, game_state)
    
    # 5. Add available voxel types information (common logic)
    # Use Unity-provided voxel_definitions (Unity always sends this)
    # For EventBatch: only show id and name (no description needed for planning)
    # For PlanPermission: show id, name, and description (needed for precise execution)
    is_executor_mode = isinstance(input_data, PlanPermission)
    voxel_definitions_from_unity = game_state.voxel_definitions if game_state else None
    _add_voxel_types_section(context_parts, voxel_definitions_from_unity, include_description=is_executor_mode)
    
    return "\n".join(context_parts)

def _add_game_state_section(context_parts: List[str], game_state: Optional[GameState]) -> None:
    """Add game state section"""
    if game_state:
        # Calculate Player position relative to Agent
        player_rel_x = game_state.player_abs_position.x - game_state.agent_abs_position.x
        player_rel_y = game_state.player_abs_position.y - game_state.agent_abs_position.y
        player_rel_z = game_state.player_abs_position.z - game_state.agent_abs_position.z
        player_rel_str = f"({player_rel_x:+d},{player_rel_y:+d},{player_rel_z:+d})"
        
        # Get directional voxel information
        directional_info = game_state.get_directional_voxels_info()
        # Get nearby voxel information
        nearby_info = game_state.get_nearby_voxels_info()
        
        context_parts.append(f"""## Game State
- Time: {game_state.timestamp}
- Player Rel Position: {player_rel_str} (relative to Agent)
- Agent Absolute Position: {game_state.agent_abs_position.to_compact_str()}
- Directional Voxels (nearest in each direction):
{directional_info}
- Nearby Voxels: {nearby_info}""")
    else:
        context_parts.append("## Game State\nUnknown - no game state provided")

def _add_history_section(context_parts: List[str], session_manager, session_id: str) -> None:
    """Add history section (limited to last 15 messages to save tokens)"""
    history = session_manager.get_history(session_id)
    if history:
        context_parts.append("## History (Last 15)")
        # Only take the last 15 messages
        recent_history = history[-15:]
        for msg in recent_history:
            msg_type = msg.get('type', 'chat')
            context_parts.append(f"- [{msg_type}] {msg['role']}: {msg['content']}")
    else:
        context_parts.append("## History\nNo history yet.")

def _add_voxel_types_section(context_parts: List[str], voxel_definitions_from_unity: Optional[List[Dict[str, Any]]] = None, include_description: bool = False) -> None:
    """Add available voxel types section
    
    Uses Unity-provided voxel_definitions (Unity always sends this in game_state).
    
    Args:
        voxel_definitions_from_unity: Voxel definitions from Unity's game_state
        include_description: If True, include description field (for executor mode). 
                            If False, only show id and name (for planner mode).
    """
    try:
        if voxel_definitions_from_unity:
            context_parts.append("## Voxel Types")
            for voxel in voxel_definitions_from_unity[:64]:  # Limit display count
                voxel_id = voxel.get('id', '?')
                voxel_name = voxel.get('name', 'Unknown')
                if include_description:
                    desc = voxel.get('description', '')
                    desc_str = f" - {desc}" if desc else ""
                    context_parts.append(f"- {voxel_name} (ID: {voxel_id}){desc_str}")
                else:
                    context_parts.append(f"- {voxel_name} (ID: {voxel_id})")
        else:
            context_parts.append("## Voxel Types\nNo types available (Unity should always provide voxel_definitions).")
    except Exception as e:
        context_parts.append(f"## Voxel Types\nError: {str(e)}")


def _process_nearby_voxels_stats(nearby_voxels) -> str:
    """Process nearby_voxels, convert to quantity statistics format"""
    if not nearby_voxels:
        return "no nearby voxels"
    
    # Count the number of each voxel type
    voxel_counts = {}
    for voxel in nearby_voxels:
        voxel_name = voxel.voxel_name if hasattr(voxel, 'voxel_name') else voxel.get('voxel_name', 'Unknown')
        voxel_counts[voxel_name] = voxel_counts.get(voxel_name, 0) + 1
    
    # Format as "name1*count1, name2*count2" format
    stats_parts = []
    for name, count in sorted(voxel_counts.items()):
        stats_parts.append(f"{name}*{count}")
    
    return f"nearby voxels: {', '.join(stats_parts)}"

def _format_command_params_compact(params) -> str:
    """Format command parameters as compact string, special handling for Position objects"""
    if isinstance(params, dict):
        compact_params = {}
        for key, value in params.items():
            if isinstance(value, dict) and all(k in value for k in ['x', 'y', 'z']):
                # This is a dictionary representation of a Position object
                compact_params[key] = f"({value['x']},{value['y']},{value['z']})"
            else:
                compact_params[key] = value
        return str(compact_params)
    else:
        return str(params)

def _process_images_in_event_batch(event_batch: EventBatch) -> None:
    """Process images in EventBatch: if 4 images found in list, merge them into 1 (2x2 grid)
    
    Processing rules:
    - AgentPerceptionPayload / AgentContinuePlanPayload: If image list has exactly 4 images, merge them
    - PlayerSpeakPayload: Single image is kept as-is, no processing
    
    This function modifies the event_batch in-place by replacing 4 images with 1 merged image.
    
    Args:
        event_batch: EventBatch to process (modified in-place)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from PIL import Image as PILImage
        
        # Process each event separately
        for idx, event in enumerate(event_batch.events):
            if not hasattr(event, 'payload'):
                continue
            
            payload = event.payload
            
            # Only process agent_perception and agent_continue_plan events (they have image lists)
            # PlayerSpeakPayload has single image, which we keep as-is
            if event.type not in ["agent_perception", "agent_continue_plan"]:
                continue
            
            # Check if this event has an image list
            if not hasattr(payload, 'image') or not payload.image or not isinstance(payload.image, list):
                continue
            
            # Collect images from this event's list
            image_list = payload.image
            valid_images = [img for img in image_list if isinstance(img, Image)]
            
            # Only process if exactly 4 images found
            if len(valid_images) != 4:
                continue
            
            #logger.info(f"[Image Processing] Detected 4 images in {event.type} event (idx: {idx}), starting merge operation (2x2 grid: 960x540 each -> 1920x1080 total)")
            
            # Merge 4 images into 1 (2x2 grid: 960x540 each -> 1920x1080 total)
            merged_image = _merge_four_images(valid_images, save_test_image=True)
            if merged_image is None:
                logger.warning(f"[Image Processing] Failed to merge images in event {idx}")
                continue
            
            #logger.info("[Image Processing] Successfully merged 4 images into 1 image (1920x1080)")
            
            # Replace the image list with merged image
            payload.image = [merged_image]
            
            #logger.info(f"[Image Processing] Replaced 4 images in event {idx} ({event.type}) with merged image")
        
    except ImportError:
        # Pillow not installed, skip image processing
        logger.warning("[Image Processing] Pillow not installed, skipping image merge operation")
        pass
    except Exception as e:
        # Log error but don't break the flow
        logger.warning(f"[Image Processing] Failed to process images: {str(e)}", exc_info=True)


def _load_image_from_image_obj(image_obj: Image):
    """Load PIL Image from Image object (supports base64, url, file_path)
    
    Args:
        image_obj: Image object containing image data
        
    Returns:
        PIL Image object or None if failed
    """
    try:
        from PIL import Image as PILImage
        import requests
        
        # Priority 1: base64
        if image_obj.base64:
            # Handle data URI format: data:image/jpeg;base64,...
            base64_data = image_obj.base64
            if ',' in base64_data:
                base64_data = base64_data.split(',', 1)[1]
            
            image_data = base64.b64decode(base64_data)
            return PILImage.open(io.BytesIO(image_data))
        
        # Priority 2: url
        elif image_obj.url:
            response = requests.get(image_obj.url, timeout=10)
            response.raise_for_status()
            return PILImage.open(io.BytesIO(response.content))
        
        # Priority 3: file_path
        elif image_obj.file_path:
            return PILImage.open(image_obj.file_path)
        
        return None
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to load image: {str(e)}")
        return None


def _merge_four_images(images: List[Image], save_test_image: bool = False) -> Optional[Image]:
    """Merge 4 images into 1 (2x2 grid: 960x540 each -> 1920x1080 total)
    
    Args:
        images: List of 4 Image objects
        save_test_image: If True, save the merged image to test json folder for testing
        
    Returns:
        Merged Image object with base64 data, or None if failed
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from PIL import Image as PILImage
        
        if len(images) != 4:
            logger.warning(f"[Image Merge] Expected 4 images, got {len(images)}")
            return None
        
        # Load all 4 images
        pil_images = []
        for idx, img_obj in enumerate(images):
            pil_img = _load_image_from_image_obj(img_obj)
            if pil_img is None:
                logger.warning(f"[Image Merge] Failed to load image {idx + 1}")
                return None
            
            original_size = pil_img.size
            # Resize to 960x540 if needed (in case sizes differ)
            if pil_img.size != (960, 540):
                #logger.info(f"[Image Merge] Resizing image {idx + 1} from {original_size} to (960, 540)")
                pil_img = pil_img.resize((960, 540), PILImage.Resampling.LANCZOS)
            else:
                #logger.info(f"[Image Merge] Image {idx + 1} size: {original_size} (no resize needed)")
                pass
            
            pil_images.append(pil_img)
        
        # Create 2x2 grid: 1920x1080 canvas
        merged = PILImage.new('RGB', (1920, 1080))
        
        # Place images in 2x2 grid:
        # [0] [1]
        # [2] [3]
        merged.paste(pil_images[0], (0, 0))      # Top-left
        merged.paste(pil_images[1], (960, 0))    # Top-right
        merged.paste(pil_images[2], (0, 540))     # Bottom-left
        merged.paste(pil_images[3], (960, 540))   # Bottom-right
        
        # Save test image if requested
        if save_test_image:
            try:
                test_image_path = "test json/merged_image_test.jpg"
                merged.save(test_image_path, format='JPEG', quality=95)
                logger.info(f"[Image Merge] Test image saved to: {test_image_path}")
            except Exception as e:
                logger.warning(f"[Image Merge] Failed to save test image: {str(e)}")
        
        # Convert to base64
        buffer = io.BytesIO()
        merged.save(buffer, format='JPEG', quality=85)
        buffer.seek(0)
        
        base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        base64_uri = f"data:image/jpeg;base64,{base64_data}"
        
        # Return new Image object with base64 data
        return Image(base64=base64_uri)
        
    except Exception as e:
        logger.warning(f"[Image Merge] Failed to merge images: {str(e)}", exc_info=True)
        return None


def _add_goal_status_section(context_parts: List[str], game_state: GameState) -> None:
    """Add goal status section"""
    
    if not game_state.pending_plans and not game_state.last_commands:
        return
    
    context_parts.append("## Goals")
    
    # Group by goal_id
    goals_dict = {}
    
    # Collect pending plans
    for plan in game_state.pending_plans:
        goal_id = plan.goal_id or "unknown"
        if goal_id not in goals_dict:
            goals_dict[goal_id] = {"plans": [], "commands": []}
        goals_dict[goal_id]["plans"].append(plan)
    
    # Collect last commands
    for command in game_state.last_commands:
        goal_id = command.goal_id or "unknown"
        if goal_id not in goals_dict:
            goals_dict[goal_id] = {"plans": [], "commands": []}
        goals_dict[goal_id]["commands"].append(command)
    
    # Output by goal
    for goal_id, goal_data in goals_dict.items():
        context_parts.append(f"\n### {goal_id}")
        
        # Plans
        if goal_data["plans"]:
            context_parts.append("**Plans:**")
            for plan in goal_data["plans"]:
                depends_info = f" (dep: {plan.depends_on})" if plan.depends_on else ""
                context_parts.append(f"- [{plan.id}] {plan.action_type}: {plan.description}{depends_info}")
        
        # Commands
        if goal_data["commands"]:
            context_parts.append("**Commands:**")
            recent_commands = goal_data["commands"][-3:]
            for command in recent_commands:
                phase_info = f" [{command.phase}]" if command.phase else ""
                compact_params = _format_command_params_compact(command.params)
                context_parts.append(f"- [{command.id}] {command.type}{phase_info}: {compact_params}")