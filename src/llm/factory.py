"""LLM工厂类 - 统一创建LangChain兼容的ChatModel"""
import logging
from typing import Any, Dict, Optional, Type
from langchain_core.language_models import BaseChatModel

from .base import BaseLLMProvider
from .providers.openai_llm import OpenAILLMProvider
from .providers.deepseek_llm import DeepSeekLLMProvider
from .providers.qwen_llm import QwenLLMProvider
from .providers.ollama_llm import OllamaLLMProvider
from .providers.lmstudio_llm import LMStudioLLMProvider
from .adapter import ChatModelAdapter

logger = logging.getLogger(__name__)


class LLMFactory:
    """LLM工厂类 - 支持多种LLM提供商"""

    # 提供者注册表
    _providers: Dict[str, Type[BaseLLMProvider]] = {
        "openai": OpenAILLMProvider,
        "deepseek": DeepSeekLLMProvider,
        "qwen": QwenLLMProvider,
        "ollama": OllamaLLMProvider,
        "lmstudio": LMStudioLLMProvider,
    }

    # 云端平台列表
    _cloud_platforms = ["openai", "deepseek", "qwen", "zhipu", "claude", "anthropic"]

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseLLMProvider]):
        """注册新的LLM提供者"""
        cls._providers[name] = provider_class
        logger.info(f"注册LLM提供者: {name}")

    @classmethod
    def create(cls, config: Dict[str, Any], existing_client: Any = None) -> BaseChatModel:
        """
        创建LLM实例

        Args:
            config: LLM配置，包含provider, model, api_key等
            existing_client: 可选的已有AI客户端实例

        Returns:
            LangChain兼容的ChatModel
        """
        provider = config.get("provider", "openai").lower()
        logger.info(f"创建LLM实例，提供者: {provider}")

        # 如果提供了已有客户端，直接包装
        if existing_client is not None:
            return ChatModelAdapter(
                ai_client=existing_client,
                model_name=f"{provider}_{config.get('model', 'unknown')}"
            )

        # 从注册表中获取提供者
        provider_class = cls._providers.get(provider)

        if provider_class is None:
            # 尝试作为云端平台处理
            if provider in cls._cloud_platforms:
                # 使用通用云端适配器
                from .providers.cloud_llm import CloudLLMProvider
                provider_class = CloudLLMProvider
            else:
                raise ValueError(f"不支持的LLM提供商: {provider}，支持的提供商: {list(cls._providers.keys())}")

        # 创建提供者实例并返回ChatModel
        provider_instance = provider_class(config)
        return provider_instance.create()

    @classmethod
    def get_supported_providers(cls) -> list:
        """获取支持的提供者列表"""
        return list(cls._providers.keys()) + cls._cloud_platforms

    @classmethod
    def is_cloud_provider(cls, provider: str) -> bool:
        """检查是否为云端提供商"""
        return provider.lower() in cls._cloud_platforms
