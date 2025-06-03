import chromadb
from openai import OpenAI
from dotenv import load_dotenv
import os
import time
import json
from typing import List, Dict, Tuple, Any, Optional
from .models import Response, Command
from .voxel_db import VoxelDB
from .fill_db import process_documents

class ChromaDBManager:
    def __init__(self, path: str):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = None
        self.ensure_collection_exists()
    
    def ensure_collection_exists(self):
        """确保ChromaDB集合存在，如果不存在则初始化"""
        try:
            self.collection = self.client.get_collection(name="unity_ai_agent")
        except Exception as e:
            print("Collection not found, initializing database...")
            process_documents()  # 初始化数据库
            self.collection = self.client.get_collection(name="unity_ai_agent")
    
    def query_by_type(self, tp: str, query_text: str, n_results: int) -> Dict:
        """按类型查询，添加错误处理和自动重试"""
        try:
            res = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where={"type": tp},
                include=["documents", "metadatas", "distances"]
            ) or {}
        except chromadb.errors.InvalidCollectionException:
            # 如果集合无效，尝试重新初始化
            print("Invalid collection, reinitializing...")
            self.ensure_collection_exists()
            # 重试查询
            res = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where={"type": tp},
                include=["documents", "metadatas", "distances"]
            ) or {}
        
        # ----------- DEBUG -------------
        print(f"\n🔍 Chroma query for '{tp}' →")
        for k, v in res.items():
            print(f"  {k}: {len(v[0]) if isinstance(v, list) and v else v}")
        return res

# ---------- constants ------------
TYPE_WEIGHTS = {
    "user_manual": 1.3,     # 手册内容权重略高
    "design_rule": 1.0
}

# Load environment variables from .env file
load_dotenv()

# Validate OpenAI API key
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("Please set OPENAI_API_KEY in your .env file")

# Configure paths for data storage
CHROMA_PATH = r"chroma_db"  # Directory for ChromaDB storage
VOXEL_DB_PATH = r"C:\Users\55485\AppData\LocalLow\DefaultCompany\AI-Agent\VoxelsDB\voxel_definitions.json"

# Initialize managers
db_manager = ChromaDBManager(CHROMA_PATH)
voxel_db = VoxelDB(VOXEL_DB_PATH)

def _similarity(distance: float) -> float:
    """Chroma 里 distance → similarity, 避免除 0."""
    return 1 / (1 + distance)

def hybrid_retrieval(query, max_results=3):
    """
    对手册 / 规则各取 max_results, 然后合并、加权、去重、排序。
    若任何一步没有命中，都会打印调试信息方便定位。
    """
    res_manual = db_manager.query_by_type("user_manual", query, max_results)
    res_rule = db_manager.query_by_type("design_rule", query, max_results)
    
    def _norm(x):
        """
        把 None、[], [[]] 都归一到 []，其余保持为一维 list。
        """
        if not x:
            return []
        # x 形如 [[]] → 取第一层
        if isinstance(x, list) and len(x) == 1 and isinstance(x[0], list):
            return x[0]
        return x                 # 一维 list 直接返回

    m_docs, m_meta, m_dist = map(_norm,
        (res_manual.get("documents"), res_manual.get("metadatas"), res_manual.get("distances")))
    r_docs, r_meta, r_dist = map(_norm,
        (res_rule.get("documents"),   res_rule.get("metadatas"),   res_rule.get("distances")))
    
    # ---------- 合并 ----------
    merged = [
        (d, m, _similarity(s) * TYPE_WEIGHTS["user_manual"])
        for d, m, s in zip(m_docs, m_meta, m_dist)
    ] + [
        (d, m, _similarity(s) * TYPE_WEIGHTS["design_rule"])
        for d, m, s in zip(r_docs, r_meta, r_dist)
    ]

    if not merged:
        print("⚠️  hybrid_retrieval() - no hits at all.")
        return {"documents": [], "metadatas": [], "relevance_scores": [], "query": query}
    
    # -------- 去重（按 manual_id / rule_id / name）--------
    seen_ids = set()
    unique   = []
    for doc, meta, score in sorted(merged, key=lambda x: x[2], reverse=True):
        uid = meta.get("manual_id") or meta.get("rule_id") or meta.get("name")
        if uid not in seen_ids:
            seen_ids.add(uid)
            unique.append((doc, meta, score))
    
     # 最终裁剪到 5 × max_results
    top_k = unique[: max_results * 5]

    # 打包
    return {
        "documents":        [d for d, _, _ in top_k],
        "metadatas":        [m for _, m, _ in top_k],
        "relevance_scores": [s for _, _, s in top_k],
        "query": query
    }
    
def build_dynamic_prompt(results, conversation_history: List[Dict[str, str]] = None):
    """
    Build the system prompt for the AI
    Args:
        results: The search results from ChromaDB
        conversation_history: List of conversation messages, each containing 'role' and 'content' (text only)
    """
    if not results['documents']:
        base_prompt = (
            "You are a helpful AI assistant for a Unity-based voxel game.\n"
            "Use the generate_response function to structure your responses.\n"
            "When you are unsure, say so briefly."
        )
    else:
        # Initialize sections for different types of content
        rule_section   = []
        manual_section = []
        
        # Process each retrieved document
        for doc, meta, score in zip(results['documents'], results['metadatas'], results['relevance_scores']):
            if meta.get('type') == "design_rule":
                rule_section.append(
                    f"- Rule: {doc[:300]}...\n"
                    f"  (Relevance: {score:.2f})\n"
                )
            else:  # user_manual
                manual_section.append(
                    f"- Manual: {doc[:300]}...\n"
                    f"  (Relevance: {score:.2f})\n"
                )
        
        base_prompt = (
            "You are an AI assistant for a Unity-based voxel game. "
            "Use the following context to help answer questions:\n\n"
            "## Design Rules\n"
            + ("\n".join(rule_section) if rule_section else "None found.")
            + "\n\n## User Manual\n"
            + ("\n".join(manual_section) if manual_section else "None found.")
            + "\n\n"
            "## Instructions\n"
            "1. Use the generate_response function to structure your response.\n"
            "2. For texture generation, include positive prompt, negative prompt, and denoise strength.\n"
            "3. For voxel creation, specify display name, base color (hex), and description.\n"
            "4. For database updates, provide section and content.\n"
            "5. For voxel queries, provide concise summaries unless details are specifically requested.\n"
        )

    # Add voxel database information
    # 默认使用简化版摘要，除非查询明确要求详细信息
    detailed = any(word in results.get('query', '').lower() for word in 
                  ['detail', 'describe', 'explain', 'tell me more', 'what is'])
    voxel_summary = voxel_db.get_voxel_summary(detailed=detailed)
    style_analysis = voxel_db.get_style_analysis() if detailed else ""
    
    base_prompt += f"\n\n{voxel_summary}"
    if detailed:
        base_prompt += f"\n\n{style_analysis}"

    # Add conversation history if available
    if conversation_history:
        base_prompt += "\n\n## Conversation History\n"
        for msg in conversation_history:
            role = msg['role'].capitalize()
            content = msg['content']
            # content is guaranteed to be text-only now
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

    # 执行RAG检索
    print("\nQuerying ChromaDB...")
    results = hybrid_retrieval(text_content)
    print(f"Found {len(results['documents'])} relevant documents")

    # 准备系统提示词
    system_prompt = build_dynamic_prompt(results, conversation_history or [])

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
                                        "enum": ["generate_texture", "create_voxel_type", "fill_db"]
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
                                                    "base_color": {"type": "string"},
                                                    "description": {"type": "string"}
                                                },
                                                "required": ["name"]
                                            },
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "section": {"type": "string"},
                                                    "content": {"type": "string"}
                                                },
                                                "required": ["section", "content"]
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
        client = OpenAI(timeout=timeout)
        response = client.chat.completions.create(
            model=model,
            messages=api_messages,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "generate_response"}}
        )

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