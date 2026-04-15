"""OpenAI LLM提供者"""
from typing import Any, Dict
from langchain_openai import ChatOpenAI

from ..base import BaseLLMProvider


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI LLM提供者"""

    def create(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.config.get("model", "gpt-4o-mini"),
            api_key=self.config.get("api_key"),
            base_url=self.config.get("base_url"),
            temperature=self.config.get("temperature", 0.7),
            max_tokens=self.config.get("max_tokens", 2048),
        )
