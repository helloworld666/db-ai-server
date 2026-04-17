"""LLM工厂 - LangChain v1.0 标准实现

使用LangChain标准的init_chat_model创建LLM实例
"""
import logging
from typing import Any, Dict, Optional

from langchain_core.language_models import BaseChatModel

from .adapter import ChatModelAdapter

logger = logging.getLogger(__name__)


def get_model_identifier(provider: str, model: str) -> str:
    """
    构建LangChain标准模型标识符

    格式: "provider:model"
    示例: "openai:gpt-4o", "anthropic:claude-3-5-sonnet"

    Args:
        provider: 提供商名称
        model: 模型名称

    Returns:
        LangChain标准模型标识符
    """
    provider_map = {
        "openai": "openai",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "deepseek": "openai",
        "qwen": "openai",
        "ollama": "ollama",
        "lmstudio": "openai",
        "openrouter": "openai",
    }
    langchain_provider = provider_map.get(provider.lower(), provider.lower())
    return f"{langchain_provider}:{model}"


def create_llm(
    config: Dict[str, Any],
    existing_client: Any = None
) -> BaseChatModel:
    """
    创建LangChain ChatModel

    优先使用LangChain标准的init_chat_model，
    对于不兼容的情况使用适配器包装。

    Args:
        config: LLM配置，包含provider, model, api_key等
        existing_client: 可选的已有AI客户端实例

    Returns:
        LangChain兼容的ChatModel
    """
    provider = config.get("provider", "openai").lower()
    model = config.get("model", "gpt-4o")
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens")

    logger.info(f"创建LLM: provider={provider}, model={model}")

    # 如果提供了已有客户端，使用适配器包装
    if existing_client is not None:
        logger.info("使用已有客户端，创建适配器")
        return ChatModelAdapter(
            ai_client=existing_client,
            model_name=f"{provider}_{model}"
        )

    # 使用LangChain标准init_chat_model
    try:
        from langchain.chat_models import init_chat_model
        model_id = get_model_identifier(provider, model)
        logger.info(f"使用init_chat_model: {model_id}")

        kwargs = {"temperature": temperature}

        local_providers = ["lmstudio", "ollama"]
        if api_key:
            kwargs["api_key"] = api_key
        elif provider.lower() in local_providers:
            kwargs["api_key"] = "not-needed-for-local-llm"

        if base_url:
            kwargs["base_url"] = base_url
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        llm = init_chat_model(model_id, **kwargs)
        logger.info(f"成功创建LLM: {model_id}, 类型: {type(llm).__name__}")
        return llm

    except ImportError:
        logger.warning("LangChain chat_models不可用，使用适配器模式")
        from ..database.llm_client import create_llm_client
        ai_client = create_llm_client(config)
        return ChatModelAdapter(
            ai_client=ai_client,
            model_name=f"{provider}_{model}"
        )
    except Exception as e:
        logger.warning(f"init_chat_model失败: {e}，使用适配器模式")
        from ..database.llm_client import create_llm_client
        ai_client = create_llm_client(config)
        return ChatModelAdapter(
            ai_client=ai_client,
            model_name=f"{provider}_{model}"
        )


def get_supported_providers() -> list:
    """获取支持的提供商列表"""
    return ["openai", "anthropic", "deepseek", "qwen", "ollama", "lmstudio", "openrouter"]
