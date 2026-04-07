"""
Ollama客户端 - 封装Ollama HTTP API调用
"""

import aiohttp
import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama HTTP客户端封装"""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434/api",
        model: str = "qwen3:8b",
        timeout: int = 120,
        max_retries: int = 3
    ):
        """
        初始化Ollama客户端
        
        Args:
            base_url: Ollama API基础URL
            model: 使用的模型名称
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        self._is_connected = False
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        num_ctx: int = 4096,
        num_predict: int = 2048,
        stream: bool = False
    ) -> str:
        """
        调用Ollama生成文本
        
        Args:
            prompt: 提示词
            system: 系统提示词
            temperature: 温度参数（0-1，越低越确定）
            num_ctx: 上下文窗口大小
            num_predict: 最大生成长度
            stream: 是否流式返回
        
        Returns:
            生成的文本
        """
        session = await self._get_session()
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict
            }
        }
        
        if system:
            payload["system"] = system
        
        logger.debug(f"Sending request to Ollama: {self.base_url}/generate")
        logger.debug(f"Model: {self.model}, Prompt length: {len(prompt)}")
        
        # 重试逻辑
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with session.post(
                    f"{self.base_url}/generate",
                    json=payload
                ) as response:
                    response.raise_for_status()
                    
                    if stream:
                        # 流式处理
                        result = []
                        async for line in response.content:
                            if line:
                                line_str = line.decode('utf-8')
                                data = json.loads(line_str)
                                if "response" in data:
                                    result.append(data["response"])
                                if data.get("done", False):
                                    break
                        return "".join(result)
                    else:
                        # 非流式处理
                        data = await response.json()
                        return data.get("response", "")
                        
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries}")
                await asyncio.sleep(2 ** attempt)  # 指数退避
                
            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Client error on attempt {attempt + 1}/{self.max_retries}: {e}")
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise RuntimeError(f"Failed to communicate with Ollama: {e}")
        
        raise RuntimeError(f"Max retries ({self.max_retries}) exceeded. Last error: {last_error}")
    
    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        num_ctx: int = 4096,
        num_predict: int = 2048
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文本
        
        Args:
            prompt: 提示词
            system: 系统提示词
            temperature: 温度参数
            num_ctx: 上下文窗口大小
            num_predict: 最大生成长度
        
        Yields:
            生成的文本片段
        """
        session = await self._get_session()
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict
            }
        }
        
        if system:
            payload["system"] = system
        
        try:
            async with session.post(
                f"{self.base_url}/generate",
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.content:
                    if line:
                        line_str = line.decode('utf-8')
                        data = json.loads(line_str)
                        if "response" in data:
                            yield data["response"]
                        if data.get("done", False):
                            break
                            
        except Exception as e:
            logger.error(f"Stream generation failed: {e}")
            raise
    
    async def chat(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.1,
        num_ctx: int = 4096
    ) -> str:
        """
        聊天模式（支持多轮对话）
        
        Args:
            messages: 消息列表，格式：[{"role": "user", "content": "..."}, ...]
            temperature: 温度参数
            num_ctx: 上下文窗口大小
        
        Returns:
            助手回复
        """
        session = await self._get_session()
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx
            }
        }
        
        try:
            async with session.post(
                f"{self.base_url}/chat",
                json=payload
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                if "message" in data and "content" in data["message"]:
                    return data["message"]["content"]
                else:
                    return ""
                    
        except Exception as e:
            logger.error(f"Chat request failed: {e}")
            raise RuntimeError(f"Failed to chat with Ollama: {e}")
    
    async def test_connection(self) -> bool:
        """
        测试Ollama连接
        
        Returns:
            是否连接成功
        """
        session = await self._get_session()
        
        try:
            async with session.get(f"{self.base_url}/tags") as response:
                response.raise_for_status()
                data = await response.json()
                
                models = [m["name"] for m in data.get("models", [])]
                logger.info(f"Available Ollama models: {models}")
                
                if self.model not in models:
                    logger.warning(f"Model '{self.model}' not found in available models")
                    logger.info(f"Pull the model with: ollama pull {self.model}")
                    return False
                
                logger.info(f"Model '{self.model}' is available")
                self._is_connected = True
                return True
                
        except aiohttp.ClientError as e:
            logger.error(f"Failed to test Ollama connection: {e}")
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error testing connection: {e}")
            self._is_connected = False
            return False
    
    async def get_model_info(self) -> Optional[Dict[str, Any]]:
        """
        获取当前模型信息
        
        Returns:
            模型信息字典
        """
        session = await self._get_session()
        
        try:
            async with session.post(
                f"{self.base_url}/show",
                json={"name": self.model}
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data
                
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return None
    
    async def list_models(self) -> list[str]:
        """
        列出所有可用模型
        
        Returns:
            模型名称列表
        """
        session = await self._get_session()
        
        try:
            async with session.get(f"{self.base_url}/tags") as response:
                response.raise_for_status()
                data = await response.json()
                return [m["name"] for m in data.get("models", [])]
                
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._is_connected
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Ollama client session closed")
