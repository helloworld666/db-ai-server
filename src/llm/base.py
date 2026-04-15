"""LLM基类定义"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


class BaseLLMProvider(ABC):
    """LLM提供者基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def create(self) -> BaseChatModel:
        """创建LLM实例"""
        pass

    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.config.get("model", "unknown")

    def get_provider_name(self) -> str:
        """获取提供者名称"""
        return self.config.get("provider", "unknown")
