"""
LangChain数据库AI服务器
基于LangChain + LangGraph的最佳实践架构

核心原则：
1. 所有配置从JSON文件读取，禁止硬编码
2. 所有提示词从配置文件读取，禁止硬编码
3. 工具调用完全由LLM自主决定
4. 数据库Schema从配置文件动态加载
"""

from .core.config.settings import Settings, get_settings
from .core.exceptions import (
    DatabaseAIError,
    ValidationError,
    SecurityError,
    ConfigurationError,
)
from .llm.factory import LLMFactory
from .agents.sql_agent import SQLAgent
from .tools.registry import ToolRegistry
from .database.connection import DatabaseConnection
from .database.schema import SchemaManager
from .security.validator import SQLValidator
from .workflows.sql_workflow import SQLWorkflow

__version__ = "2.0.0"
__all__ = [
    "Settings",
    "get_settings",
    "LLMFactory",
    "SQLAgent",
    "ToolRegistry",
    "DatabaseConnection",
    "SchemaManager",
    "SQLValidator",
    "SQLWorkflow",
    "DatabaseAIError",
    "ValidationError",
    "SecurityError",
    "ConfigurationError",
]
