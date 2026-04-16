"""LLM模块 - LangChain v1.0 标准接口

使用LangChain标准API创建和管理LLM实例
"""
from .factory import create_llm, get_model_identifier
from .adapter import ChatModelAdapter

__all__ = ["create_llm", "get_model_identifier", "ChatModelAdapter"]
