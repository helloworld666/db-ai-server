"""LLM模块 - LangChain标准API

使用LangChain v1.0官方推荐的init_chat_model统一入口
"""
from .factory import create_llm, get_model_identifier

__all__ = ["create_llm", "get_model_identifier"]
