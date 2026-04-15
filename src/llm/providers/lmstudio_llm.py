"""LM Studio LLM提供者"""
from typing import Any, Dict
from langchain_openai import ChatOpenAI

from ..base import BaseLLMProvider


class LMStudioLLMProvider(BaseLLMProvider):
    """LM Studio LLM提供者"""

    DEFAULT_BASE_URL = "http://localhost:1234/v1"
    DEFAULT_MODEL = "local-model"

    def create(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.config.get("model", self.DEFAULT_MODEL),
            api_key="not-needed",
            base_url=self.config.get("base_url") or self.DEFAULT_BASE_URL,
            temperature=self.config.get("temperature", 0.7),
            max_tokens=self.config.get("max_tokens", 2048),
        )
