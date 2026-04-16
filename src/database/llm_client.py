"""AI客户端工厂 - 用于创建底层AI客户端

用于适配器模式，当init_chat_model不兼容时使用
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def create_llm_client(config: Dict[str, Any]) -> Any:
    """
    创建底层AI客户端

    Args:
        config: 配置字典，包含provider, model, api_key等

    Returns:
        AI客户端实例
    """
    provider = config.get("provider", "openai").lower()
    model = config.get("model", "gpt-4o")
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    temperature = config.get("temperature", 0.7)

    logger.info(f"创建AI客户端: provider={provider}, model={model}")

    if provider == "openai":
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            return OpenAICompatibleClient(client, model, temperature)
        except ImportError:
            logger.error("openai包未安装")
            raise

    elif provider == "deepseek":
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url or "https://api.deepseek.com/v1"
            )
            return OpenAICompatibleClient(client, model, temperature)
        except ImportError:
            logger.error("openai包未安装")
            raise

    elif provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(model=model, temperature=temperature)
        except ImportError:
            logger.error("langchain-ollama包未安装")
            raise

    else:
        # 默认使用OpenAI兼容接口
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            return OpenAICompatibleClient(client, model, temperature)
        except ImportError:
            logger.error("openai包未安装")
            raise


class OpenAICompatibleClient:
    """OpenAI兼容客户端包装器"""

    def __init__(self, client: Any, model: str, temperature: float = 0.7):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.base_url = getattr(client, 'base_url', None)

    async def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """生成响应"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature)
        )

        return response.choices[0].message.content
