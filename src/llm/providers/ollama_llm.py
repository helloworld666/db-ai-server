"""Ollama LLM提供者"""
from typing import Any, Dict
from langchain_ollama import ChatOllama

from ..base import BaseLLMProvider


class OllamaLLMProvider(BaseLLMProvider):
    """Ollama LLM提供者"""

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama3"

    def create(self) -> ChatOllama:
        base_url = self.config.get("base_url") or self.DEFAULT_BASE_URL

        return ChatOllama(
            model=self.config.get("model", self.DEFAULT_MODEL),
            base_url=base_url,
            temperature=self.config.get("temperature", 0.7),
        )
