"""通用云端LLM提供者"""
from typing import Any, Dict
from langchain_openai import ChatOpenAI

from ..base import BaseLLMProvider


class CloudLLMProvider(BaseLLMProvider):
    """通用云端LLM提供者 - 支持智谱AI、Claude等OpenAI兼容API"""

    PLATFORM_CONFIGS = {
        "zhipu": {
            "name": "智谱AI",
            "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
            "default_model": "glm-4-flash",
        },
        "claude": {
            "name": "Claude",
            "default_base_url": "https://api.anthropic.com/v1",
            "default_model": "claude-3-5-haiku-20241022",
        },
    }

    def create(self) -> ChatOpenAI:
        provider = self.config.get("provider", "unknown")
        platform_config = self.PLATFORM_CONFIGS.get(provider, {})

        return ChatOpenAI(
            model=self.config.get("model") or platform_config.get("default_model", "gpt-4o-mini"),
            api_key=self.config.get("api_key", ""),
            base_url=self.config.get("base_url") or platform_config.get("default_base_url"),
            temperature=self.config.get("temperature", 0.7),
            max_tokens=self.config.get("max_tokens", 2048),
        )
