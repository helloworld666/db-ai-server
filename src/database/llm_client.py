"""AI客户端工厂 - 底层AI客户端管理

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
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            return OpenAICompatibleClient(client, model, temperature)
        except ImportError:
            logger.error("openai包未安装")
            raise

    elif provider in ("deepseek", "qwen", "lmstudio"):
        try:
            from openai import AsyncOpenAI
            default_base_url = {
                "deepseek": "https://api.deepseek.com/v1",
                "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "lmstudio": base_url or "http://127.0.0.1:1234/v1",
            }
            client = AsyncOpenAI(
                api_key=api_key or "not-needed",
                base_url=base_url or default_base_url.get(provider)
            )
            return OpenAICompatibleClient(client, model, temperature)
        except ImportError:
            logger.error("openai包未安装")
            raise

    elif provider == "anthropic":
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=api_key)
            return AnthropicClient(client, model, temperature)
        except ImportError:
            logger.error("anthropic包未安装")
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
            client = AsyncOpenAI(api_key=api_key or "not-needed", base_url=base_url)
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

    async def generate_with_tools(
        self,
        prompt: str,
        system: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """使用工具调用生成响应"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            tools=tools,
            tool_choice="auto"
        )

        choice = response.choices[0]
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            return {
                "content": choice.message.content or "",
                "tool_calls": [
                    {
                        "name": tc.function.name,
                        "args": json.loads(tc.function.arguments)
                    }
                    for tc in choice.message.tool_calls
                ]
            }
        return {"content": choice.message.content or ""}


class AnthropicClient:
    """Anthropic客户端包装器"""

    def __init__(self, client: Any, model: str, temperature: float = 0.7):
        self.client = client
        self.model = model
        self.temperature = temperature

    async def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """生成响应"""
        messages = [{"role": "user", "content": prompt}]
        response = await self.client.messages.create(
            model=self.model,
            messages=messages,
            system=system,
            temperature=kwargs.get("temperature", self.temperature)
        )
        return response.content[0].text
