"""
DB-AI-Server MCP Server v5.0
基于LangChain标准API的AI数据库SQL生成服务器

核心原则：
1. 所有配置从JSON文件读取，禁止硬编码
2. 所有提示词从配置文件读取，禁止硬编码
3. 工具调用完全由LLM自主决定
4. 数据库Schema从配置文件动态加载
5. 使用LangChain标准API (init_chat_model, @tool装饰器)
"""

from .core.config.settings import Settings, get_settings
from .core.exceptions import (
    DatabaseAIError,
    ValidationError,
    SecurityError,
    ConfigurationError,
)
from .llm.factory import create_llm, get_model_identifier
from .agents.react_agent import ReActAgent, create_react_agent
from .database.connection import DatabaseConnection
from .database.schema import SchemaManager
from .security.validator import SQLValidator

__version__ = "5.0.0"
__all__ = [
    "Settings",
    "get_settings",
    "create_llm",
    "get_model_identifier",
    "ReActAgent",
    "create_react_agent",
    "DatabaseConnection",
    "SchemaManager",
    "SQLValidator",
    "DatabaseAIError",
    "ValidationError",
    "SecurityError",
    "ConfigurationError",
]
