"""
LM Studio 客户端 - 封装 LM Studio HTTP API 调用（OpenAI 兼容 API）
"""

import aiohttp
import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator

logger = logging.getLogger(__name__)


class LMStudioClient:
    """LM Studio HTTP客户端封装（OpenAI 兼容 API）"""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 120,
        max_retries: int = 3
    ):
        """
        初始化 LM Studio 客户端

        Args:
            base_url: LM Studio API 基础 URL（使用 OpenAI 兼容路径 /v1）
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
        """获取或创建 HTTP 会话"""
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
        调用 LM Studio 生成文本（使用 chat/completions API）

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

        # 构建 OpenAI 兼容的消息格式
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "max_tokens": num_predict  # 直接使用 max_tokens，而不是 extra_options
        }

        # 移除 num_ctx 参数，避免 LM Studio API 400 错误

        logger.debug(f"Sending request to LM Studio: {self.base_url}/chat/completions")
        logger.debug(f"Model: {self.model}, Prompt length: {len(prompt)}")

        # 重试逻辑
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload
                ) as response:
                    response.raise_for_status()

                    if stream:
                        # 流式处理
                        result = []
                        async for line in response.content:
                            if line:
                                line_str = line.decode('utf-8').strip()
                                if line_str.startswith('data: '):
                                    line_str = line_str[6:]
                                if line_str == '[DONE]':
                                    break
                                if line_str:
                                    try:
                                        data = json.loads(line_str)
                                        if "choices" in data and len(data["choices"]) > 0:
                                            delta = data["choices"][0].get("delta", {})
                                            if "content" in delta:
                                                result.append(delta["content"])
                                    except json.JSONDecodeError:
                                        continue
                        return "".join(result)
                    else:
                        # 非流式处理
                        data = await response.json()
                        if "choices" in data and len(data["choices"]) > 0:
                            return data["choices"][0].get("message", {}).get("content", "")
                        else:
                            logger.warning(f"Unexpected response format: {data}")
                            return ""

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
                raise RuntimeError(f"Failed to communicate with LM Studio: {e}")

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

        # 构建 OpenAI 兼容的消息格式
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": num_predict
        }

        # 移除 num_ctx 参数，避免 LM Studio API 400 错误

        try:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.content:
                    if line:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data: '):
                            line_str = line_str[6:]
                        if line_str == '[DONE]':
                            break
                        if line_str:
                            try:
                                data = json.loads(line_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                continue

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
            "temperature": temperature
        }

        # 移除 num_ctx 参数，避免 LM Studio API 400 错误

        try:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                response.raise_for_status()
                data = await response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0].get("message", {}).get("content", "")
                else:
                    return ""

        except Exception as e:
            logger.error(f"Chat request failed: {e}")
            raise RuntimeError(f"Failed to chat with LM Studio: {e}")

    async def test_connection(self) -> bool:
        """
        测试 LM Studio 连接

        Returns:
            是否连接成功
        """
        session = await self._get_session()

        try:
            # 尝试获取模型列表（LM Studio 可能不支持 /models，使用简单的聊天测试）
            # 先尝试发送一个简单的测试请求
            test_payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
                "max_tokens": 5,
                "temperature": 0.1
            }

            async with session.post(
                f"{self.base_url}/chat/completions",
                json=test_payload
            ) as response:
                response.raise_for_status()
                data = await response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    logger.info(f"LM Studio connection successful, model: {self.model}")
                    self._is_connected = True
                    return True
                else:
                    logger.warning(f"LM Studio returned unexpected response format: {data}")
                    return False

        except aiohttp.ClientError as e:
            logger.error(f"Failed to test LM Studio connection: {e}")
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
            # LM Studio 可能没有独立的模型信息接口，返回基本信息
            return {
                "model": self.model,
                "base_url": self.base_url
            }

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
            # LM Studio 可能不支持列出所有模型，返回当前模型
            return [self.model]

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._is_connected

    async def close(self):
        """关闭 HTTP 会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("LM Studio client session closed")
