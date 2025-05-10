from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import chromadb
import json
import yaml 

from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, Any, List

# setting the environment
CHROMA_PATH = r"chroma_db"
MANUAL_DIR = "manuals"
RULE_DIR   = "rules"

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="unity_ai_agent")

# ---------- 3.1 解析 front-matter ----------
def split_frontmatter(raw: str) -> tuple[Dict[str, Any], str]:
    if raw.startswith("---"):
        _, fm, body = raw.split("---", 2)
        meta = yaml.safe_load(fm) or {}
        return meta, body.strip()
    return {}, raw

# ---------- 3.2 加载目录下所有文本 ----------
def load_text_dir(dir_path: str, doc_type: str) -> List[Document]:
    docs = []
    for fp in Path(dir_path).rglob("*"):
        if fp.suffix.lower() not in {".txt", ".md", ".markdown"}:
            continue
        text = fp.read_text(encoding="utf-8")
        meta, body = split_frontmatter(text)
        meta.update({
            "type": doc_type,
            "source": fp.name,
            "name": meta.get("name", fp.stem),
            "created_at": meta.get("created_at", datetime.now(UTC).isoformat())
        })
        docs.append(Document(page_content=body, metadata=meta))
    return docs
    
def normalize_metadata(orig_meta: Dict[str, Any]) -> Dict[str, Any]:
    """元数据标准化处理"""
    base = {
        "type": orig_meta.get("type", "unknown"),
        "version": float(orig_meta.get("version", 1.0)),
        "created_at": orig_meta.get("created_at", datetime.now(UTC).isoformat()),
        "source": orig_meta.get("source", "unknown"),
        "tags": ",".join(orig_meta.get("tags", [])) if isinstance(orig_meta.get("tags"), list) else orig_meta.get("tags", "")
    }

    # 类型特定处理
    if base["type"] == "design_rule":
        base |= {
            "rule_id": orig_meta["rule_id"],  # 强制转换为字符串
            "condition": orig_meta.get("condition", ""), # "condition": json.loads(orig_meta.get("condition", "{}")),
            "action": orig_meta.get("action", ""),
            "is_active": orig_meta.get("is_active", True),
            "format_template": orig_meta.get("format_template", "")
        }

    elif base["type"] == "user_manual":
        base |= {
            "manual_id": orig_meta["manual_id"],
            "condition": orig_meta.get("condition", ""), 
            "action": orig_meta.get("action", ""),
            "format_template": orig_meta.get("format_template", "")
        }
        
     # 其余字段原样保留
    for k, v in orig_meta.items():
        base.setdefault(k, v)
    return base

    return base

# splitting the documents
class RuleAwareSplitter(RecursiveCharacterTextSplitter):
    def split_documents(self, docs):
        processed = []
        for doc in docs:
            if doc.metadata.get('type') == 'design_rule':
                # 保持规则文档完整性
                processed.append(doc)
            else:
                # 原有分块逻辑
                processed.extend(super().split_documents([doc])) # 手册分块 ！！！待测试！！！
        return processed

def process_documents() -> None:
    """处理文档并将其存储到 Chroma 数据库"""
    # 删除旧的集合
    try:
        chroma_client.delete_collection(name="unity_ai_agent")
        print("Successfully deleted old collection")
    except Exception as e:
        print(f"Error deleting old collection: {e}")

    # 创建新的集合
    collection = chroma_client.create_collection(name="unity_ai_agent")

    # 获取规则
    manuals = load_text_dir(MANUAL_DIR, "user_manual")
    rules = load_text_dir(RULE_DIR, "design_rule")

    # 合并所有文档源
    all_docs = rules + manuals

    # 初始化文本分割器
    text_splitter = RuleAwareSplitter.from_tiktoken_encoder(
        chunk_size=300,
        chunk_overlap=150,
        separators=["\n\n", "\n", "(?<=。)", " "],
        keep_separator=True
    )

    # 分割文档
    chunks = text_splitter.split_documents(all_docs)

    # 准备数据
    documents = []
    metadata = []
    ids = []

    # 处理每个文块
    for i, chunk in enumerate(chunks):
        try:
            norm_meta = normalize_metadata(chunk.metadata)
        except ValueError as e:
            print(f"Skipping invalid metadata: {e}")
            continue
        documents.append(chunk.page_content)
        metadata.append(norm_meta)
        ids.append(f"DOC_{datetime.now().strftime('%Y%m%d')}_{i}")

    # 将数据写入数据库
    if documents:
        collection.add(
            documents=documents,
            metadatas=metadata,
            ids=ids
        )
        print(f"Successfully added {len(documents)} documents")
        return f"Successfully added {len(documents)} documents"
    else:
        print("No documents to add after filtering")
        return "No documents to add after filtering"

# 在直接运行此脚本时执行处理：
if __name__ == '__main__':
    process_documents()