"""
OpenAI 结构化输出 Schema 管理

这个模块集中管理所有 OpenAI API 调用中使用的 JSON Schema 定义。
遵循单一职责原则，将 schema 定义与业务逻辑分离。
"""

from typing import Dict, Any, Type
from pydantic import BaseModel
from core.models.protocol import SimplePlannerResponse, SimpleExecutorResponse


def _add_strict_properties(obj: Any) -> None:
    """
    递归为所有对象类型添加 additionalProperties: false
    这是 OpenAI strict mode 的要求
    
    Args:
        obj: 要处理的 schema 对象
    """
    if isinstance(obj, dict):
        if "type" in obj and obj["type"] == "object":
            obj["additionalProperties"] = False
        for value in obj.values():
            _add_strict_properties(value)
    elif isinstance(obj, list):
        for item in obj:
            _add_strict_properties(item)


def create_openai_schema(
    model_class: Type[BaseModel], 
    schema_name: str, 
    strict: bool = True
) -> Dict[str, Any]:
    """
    通用的 OpenAI schema 创建器
    
    Args:
        model_class: Pydantic 模型类
        schema_name: Schema 名称
        strict: 是否启用严格模式
        
    Returns:
        OpenAI response_format 格式的 schema 定义
    """
    schema = model_class.model_json_schema()
    
    if strict:
        _add_strict_properties(schema)
    
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "schema": schema,
            "strict": strict
        }
    }


def get_planner_response_schema(strict: bool = True) -> Dict[str, Any]:
    """
    获取 SimplePlannerResponse 的 OpenAI 结构化输出 schema
    LLM只需要提供核心信息，ID由Python自动生成
    
    Args:
        strict: 是否启用严格模式。True为严格模式，False为兼容模式
    
    Returns:
        Dict[str, Any]: OpenAI response_format 格式的 schema 定义
    """
    return create_openai_schema(SimplePlannerResponse, "SimplePlannerResponse", strict)


# =============================================================================
# 其他 Schema 定义
# =============================================================================

def get_executor_response_schema(strict: bool = True) -> Dict[str, Any]:
    """
    获取 CommandBatch 的 OpenAI 结构化输出 schema
    
    Args:
        strict: 是否启用严格模式。True为严格模式，False为兼容模式
    
    Returns:
        Dict[str, Any]: OpenAI response_format 格式的 schema 定义
    """
    return create_openai_schema(SimpleExecutorResponse, "SimpleExecutorResponse", strict)

