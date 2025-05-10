import chromadb
from openai import OpenAI
from dotenv import load_dotenv
import os
import time

from typing import List, Dict, Tuple, Any

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

# Initialize ChromaDB client and create/get collection
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="unity_ai_agent")

# ---------- helper --------------
def _similarity(distance: float) -> float:
    """Chroma 里 distance → similarity, 避免除 0."""
    return 1 / (1 + distance)

def hybrid_retrieval(query, max_results=3):
    """
    对手册 / 规则各取 max_results, 然后合并、加权、去重、排序。
    若任何一步没有命中，都会打印调试信息方便定位。
    """
    
    def _query_by_type(tp: str):
        res = collection.query(
            query_texts=[query],
            n_results=max_results,
            where={"type": tp},
            include=["documents", "metadatas", "distances"]
        ) or {}                      # ← Chroma 可能返回 None
         # ----------- DEBUG -------------
        print(f"\n🔍 Chroma query for '{tp}' →")
        for k, v in res.items():
            print(f"  {k}: {len(v[0]) if isinstance(v, list) and v else v}")
        return res
        
    res_manual = _query_by_type("user_manual")
    res_rule   = _query_by_type("design_rule")    
    
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
        return {"documents": [], "metadatas": [], "relevance_scores": []}
    
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
        "relevance_scores": [s for _, _, s in top_k]
    }
    



def build_dynamic_prompt(results):
    """
    把检索结果整理成系统 prompt 兼容新字段:
      manual:  manual_id + condition + action + format_template
      rule:    rule_id   + condition + action + format_template
    """
    # Return default prompt if no results found
    if not results['documents']:
        return """
    return (
            "You are a helpful AI assistant.\n\n"
            "When you are unsure, say so briefly. "
            "If a structured output is needed, always follow the "
            'format described in the user\'s request.'
        )
    """
    
    # Initialize sections for different types of content
    rule_section   = []
    manual_section = []
    
    # Process each retrieved document
    for doc, meta, score in zip(results['documents'], results['metadatas'], results['relevance_scores']):
         # 提取公用字段
        fmt   = meta.get("format_template", "")
        cond  = meta.get("condition", "N/A")
        act   = meta.get("action",   "N/A")
        ver   = meta.get("version",  1.0)
        
        if meta.get('type') == "design_rule":
            rid = meta.get("rule_id") or meta.get("name", "undefined")
            rule_section.append(
                f"- **Rule** `{rid}` (v{ver})\n"
                f"  - **Trigger**: `{cond}`\n"
                f"  - **Action** : `{act}`\n"
                f"  - **Template**:\n    ```json\n{fmt}\n    ```\n"
                f"  - **Content**: {doc[:500]}...\n"
            )
        else:  # user_manual
            mid = meta.get("manual_id") or meta.get("name", "undefined")
            sec = meta.get("section", "General")
            manual_section.append(
                f"- **Manual** `{mid}` | Section: *{sec}* (v{ver})\n"
                f"  - **Trigger**: `{cond}`\n"
                f"  - **Action** : `{act}`\n"
                f"  - **Template**:\n    ```json\n{fmt}\n    ```\n"
                f"  - **Excerpt** : {doc[:300]}...\n"
            )
    
    # ---------- 拼接最终 prompt ----------
    print (
    "You are an AI assistant embedded in a Unity simulation. "
    "Use the rules and manuals below to decide what output format "
    "to emit.\n\n"
    "## Design Rules (dynamic)\n"
    + ("\n".join(rule_section) if rule_section else "None found.")
    + "\n\n## User Manuals (static)\n"
    + ("\n".join(manual_section) if manual_section else "None found.")
    + "\n\n"
    "## How to reply\n"
    "1. Briefly explain your reasoning (2-3 sentences max).\n"
    "2. Follow exactly the format specified in the relevant manual's format_template. "
    "Do not modify or combine formats. Some actions require JSON while others use "
    "different formats (like tags).\n"
    "3. When multiple actions are needed, output each in its correct format "
    "one after another in the appropriate order.\n"
    )
    return (
    "You are an AI assistant embedded in a Unity simulation. "
    "Use the rules and manuals below to decide what output format "
    "to emit.\n\n"
    "## Design Rules (dynamic)\n"
    + ("\n".join(rule_section) if rule_section else "None found.")
    + "\n\n## User Manuals (static)\n"
    + ("\n".join(manual_section) if manual_section else "None found.")
    + "\n\n"
    "## How to reply\n"
    "1. Briefly explain your reasoning (2-3 sentences max).\n"
    "2. Follow exactly the format specified in the relevant manual's format_template. "
    "Do not modify or combine formats. Some actions require JSON while others use "
    "different formats (like tags).\n"
    "3. When multiple actions are needed, output each in its correct format "
    "one after another in the appropriate order.\n"
    )

def call_openai_api(
    messages: List[Dict[str, Any]],
    model: str = "gpt-4o-mini", 
    timeout: float = 90.0
    ) -> Tuple[str, Dict[str, int]]:
    """
    """
    # ------- 拆内容 ---------
    text_content  = next((m["text"] for m in messages if m["type"] == "text"), "")
    image_content = next(
        (m["image_url"]["url"] if isinstance(m["image_url"], dict) else m["image_url"]
         for m in messages if m["type"] == "image_url"),
        None
    )
    # ------------------------

    # Use text content for document retrieval
    print("\nQuerying ChromaDB...")
    query_start = time.time()
    search_query = f"{text_content} (This query includes an image for analysis)" if image_content else text_content
    results = hybrid_retrieval(search_query)
    print(f"ChromaDB query took {time.time() - query_start:.2f} seconds")

    # 检查检索结果是否为空
    if not results["documents"]:
        return "No relevant documents found in the database. Please try a different query.", {}

    # Generate system prompt
    system_prompt = build_dynamic_prompt(results)
    print(f"Total prompt size: {len(system_prompt)} characters")
    
    # Initialize OpenAI client with extended timeout
    client = OpenAI(
        timeout=timeout  # Extended timeout for longer responses
    )
    
    # Prepare message list
    full_messages = [
        {"role": "system", "content": system_prompt},
    ]
    
    # If image exists, add to user message
    if image_content:
        full_messages.append({
            "role": "user",
            "content": [
                {"type": "text", 
                 "text": f"{text_content} (This query includes an image for analysis)"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_content,
                        "detail": "auto"
                    }
                }
            ]
        })
    else:
        full_messages.append({
            "role": "user",
            "content": text_content
        })
    
    # Make API call to OpenAI
    try:
        print("\nCalling OpenAI API...")
        api_start = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=full_messages
        )
        print(f"OpenAI API call took {time.time() - api_start:.2f} seconds")

        # Get token usage information
        token_usage = {
            'prompt_tokens': response.usage.prompt_tokens,
            'completion_tokens': response.usage.completion_tokens,
            'total_tokens': response.usage.total_tokens
        }
        
        answer=response.choices[0].message.content

        # Return both the response content and token usage
        return answer, token_usage
    except Exception as e:
        print("OpenAI error:", e)
        return "", {}
    # -------- 新增保险杠 -------------
    return "", {}              # 万一上面提前跳出了 try，还能兜底

# Main execution flow in py
if __name__ == "__main__":
    # Get user input
    #user_query = input("What would you like to know about?\n\n")
    messages: list[dict] = [{"type": "text", "text": "Hi, what do you know"}]

    response_content, token_usage = call_openai_api(messages)
    if response_content:
        print("\n\n---------------------\n\n")
        print(response_content)
        print("\n\nToken Usage:")
        print(f"Prompt tokens: {token_usage.get('prompt_tokens', 0)}")
        print(f"Completion tokens: {token_usage.get('completion_tokens', 0)}")
        print(f"Total tokens: {token_usage.get('total_tokens', 0)}")