import os
from openai import OpenAI
from dotenv import load_dotenv
import json
from typing import List, Dict, Any, Optional, Tuple
from .models import Response, Command
from .voxel_db import VoxelDB

# Load environment variables from .env file
load_dotenv()

# Validate OpenAI API key
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("Please set OPENAI_API_KEY in your .env file")

# Configure paths for data storage
VOXEL_DB_PATH = r"C:\Users\55485\AppData\LocalLow\DefaultCompany\AI-Agent\VoxelsDB\voxel_definitions.json"
MANUAL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "manuals", "voxel_world_manual.md")
voxel_db = VoxelDB(VOXEL_DB_PATH)

def load_game_manual():
    """Load the game manual content"""
    try:
        with open(MANUAL_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not load game manual: {e}")
        return ""

def build_prompt(conversation_history: List[Dict[str, str]] = None):
    """
    Build the system prompt for the AI
    Args:
        conversation_history: List of conversation messages, each containing 'role' and 'content'
    """
    # Load game manual
    game_manual = load_game_manual()
    
    base_prompt = (
        "You are an AI assistant for a voxel world. Keep responses concise and focus on executing commands.\n\n"
        
        f"## Game Manual\n{game_manual}\n\n"
        
        "## Available Commands\n\n"
        
        "1. Generate Texture (generate_texture):\n"
        "   - Purpose: Create textures for voxels\n"
        "   - Parameters:\n"
        "     * pprompt (required): Format 'Texture of [descriptive words], seamless'\n"
        "     * nprompt (optional): Default 'text, blurry, watermark'\n"
        "     * denoise (optional): Default 1.0\n"
        "   - IMPORTANT: Must be used with create_voxel_type or update_voxel_type\n\n"
        
        "2. Create Voxel Type (create_voxel_type):\n"
        "   - Purpose: Create new voxel types\n"
        "   - Parameters:\n"
        "     * name (required): Unique, descriptive name\n"
        "     * description (required): Brief description\n"
        "   - Must reference existing types in voxel database\n\n"
        
        "3. Update Voxel Type (update_voxel_type):\n"
        "   - Purpose: Modify existing voxel types\n"
        "   - Parameters:\n"
        "     * name (required): Existing voxel name\n"
        "     * description (optional): New description\n"
        "     * texture (optional): New texture path\n"
        "   - Must select target from existing voxel database\n\n"
        
        "## Response Guidelines\n\n"
        
        "1. Keep answers brief and focused on commands\n"
        "2. Never use generate_texture alone\n"
        "3. Command sequences:\n"
        "   - New voxel: generate_texture + create_voxel_type\n"
        "   - Update voxel: generate_texture + update_voxel_type (or update_voxel_type alone)\n"
        "4. Maximum response length: 500 words\n\n"
        
        "## Example Command Sequence:\n"
        "{\n"
        "  \"commands\": [\n"
        "    {\n"
        "      \"type\": \"generate_texture\",\n"
        "      \"params\": {\n"
        "        \"pprompt\": \"Texture of polished marble with gold veins, seamless\"\n"
        "      }\n"
        "    },\n"
        "    {\n"
        "      \"type\": \"create_voxel_type\",\n"
        "      \"params\": {\n"
        "        \"name\": \"Golden Marble\",\n"
        "        \"description\": \"Luxurious marble with gold veins\"\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )

    # Add voxel database information
    voxel_summary = voxel_db.get_voxel_summary(detailed=False)
    base_prompt += f"\n\n## Current Voxel Database Summary:\n{voxel_summary}"

    # Add conversation history if available
    if conversation_history:
        base_prompt += "\n\n## Conversation History\n"
        for msg in conversation_history:
            role = msg['role'].capitalize()
            content = msg['content']
            base_prompt += f"{role}: {content}\n"

    return base_prompt

def call_openai_api(
    messages: List[Dict[str, Any]],
    model: str = "gpt-4o-mini", 
    timeout: float = 90.0,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Tuple[str, Dict[str, int]]:
    """
    使用function calling调用OpenAI API
    Args:
        messages: 当前的消息
        model: 使用的模型名称
        timeout: API超时时间
        conversation_history: 历史对话记录
    """
    # 提取文本和图片内容
    text_content = next((m["text"] for m in messages if m["type"] == "text"), "")
    image_content = next(
        (m["image_url"] for m in messages if m["type"] == "image_url"),
        None
    )

    # 准备系统提示词
    system_prompt = build_prompt(conversation_history)

    # 定义函数工具
    tools = [
        {
            "type": "function",
            "function": {
                "name": "generate_response",
                "description": "Generate a structured response with optional commands",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "answer": {
                            "type": "string",
                            "description": "The answer to the user's question"
                        },
                        "commands": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["generate_texture", "create_voxel_type", "update_voxel_type"]
                                    },
                                    "params": {
                                        "type": "object",
                                        "oneOf": [
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "voxel_name": {"type": "string"},
                                                    "pprompt": {"type": "string"},
                                                    "nprompt": {"type": "string"},
                                                    "denoise": {"type": "number"}
                                                },
                                                "required": ["pprompt"]
                                            },
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "description": {"type": "string"},
                                                    "is_transparent": {"type": "boolean"}
                                                },
                                                "required": ["name"]
                                            },
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "voxel_id": {"type": "integer"},
                                                    "description": {"type": "string"},
                                                    "texture": {"type": "string"},
                                                    "is_transparent": {"type": "boolean"}
                                                },
                                                "required": ["name"]
                                            }
                                        ]
                                    }
                                },
                                "required": ["type", "params"]
                            }
                        }
                    },
                    "required": ["answer"]
                }
            }
        }
    ]
    
    # 准备消息
    api_messages = [
        {"role": "system", "content": system_prompt},
    ]
    
    # If image exists, add to user message
    if image_content:
        api_messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": text_content},
                {"type": "image_url", "image_url": {"url": image_content, "detail": "auto"}}
            ]
        })
    else:
        api_messages.append({"role": "user", "content": text_content})

    # 调用API
    try:
        print("\nDEBUG - Calling OpenAI API with messages:", json.dumps(api_messages, indent=2))
        print("\nDEBUG - Using tools:", json.dumps(tools, indent=2))
        
        client = OpenAI(timeout=timeout)
        response = client.chat.completions.create(
            model=model,
            messages=api_messages,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "generate_response"}}
        )

        print("\nDEBUG - Raw API response:", response)
        print("\nDEBUG - Tool calls:", response.choices[0].message.tool_calls)

        # Get token usage information
        token_usage = {
            'prompt_tokens': response.usage.prompt_tokens,
            'completion_tokens': response.usage.completion_tokens,
            'total_tokens': response.usage.total_tokens
        }

        # 处理响应
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "generate_response":
                # 解析函数调用参数
                args = json.loads(tool_call.function.arguments)
                
                # 创建响应对象
                response_model = Response(
                    answer=args["answer"],
                    commands=[Command(**cmd) for cmd in args.get("commands", [])]
                )
                
                # 返回JSON格式的响应
                return json.dumps(response_model.model_dump(), indent=2), token_usage
                
        return json.dumps({"answer": response.choices[0].message.content, "commands": []}, indent=2), token_usage
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error details:\n{error_details}")
        raise

# Main execution flow in py
if __name__ == "__main__":
    # Initialize conversation history
    conversation_history = []
    
    while True:
        try:
            # Get user input
            user_input = input("\nWhat would you like to know about? (or type 'exit' to quit)\n\n")
            
            if user_input.lower() == 'exit':
                break
                
            # Create message format for API call (can include image)
            messages = [{"type": "text", "text": user_input}]
            
            # Add user message to history (text only)
            conversation_history.append({
                "role": "user",
                "content": user_input  # Only save text content
            })
            
            # Call API with history
            response_content, token_usage = call_openai_api(
                messages,
                conversation_history=conversation_history
            )
            
            if response_content:
                print("\n\n---------------------\n\n")
                print(response_content)
                print("\n\nToken Usage:")
                print(f"Prompt tokens: {token_usage.get('prompt_tokens', 0)}")
                print(f"Completion tokens: {token_usage.get('completion_tokens', 0)}")
                print(f"Total tokens: {token_usage.get('total_tokens', 0)}")
                
                # Parse response and add to history (text only)
                try:
                    response_data = json.loads(response_content)
                    assistant_message = response_data.get("answer", response_content)
                except json.JSONDecodeError:
                    assistant_message = response_content
                
                # Ensure assistant message is text only
                if isinstance(assistant_message, list):
                    # If message is a list of content types, extract only text
                    assistant_message = next(
                        (item.get('text') for item in assistant_message if isinstance(item, dict) and 'text' in item),
                        str(assistant_message)  # fallback to string representation
                    )
                
                conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })
                
                # Keep only last N messages to prevent context from growing too large
                MAX_HISTORY = 10  # Adjust this value as needed
                if len(conversation_history) > MAX_HISTORY * 2:  # *2 because each QA pair is 2 messages
                    conversation_history = conversation_history[-MAX_HISTORY * 2:]
                    
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            continue