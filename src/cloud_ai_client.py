"""
云端AI客户端 - 支持Deep Seek, 通义千问, 智谱AI, OpenAI, Claude等云端AI平台
基于OpenAI兼容API封装，统一接口设计
"""

import aiohttp
import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator

logger = logging.getLogger(__name__)


class CloudAIClient:
    """
    云端AI客户端 - 支持多种云AI平台的统一接口
    支持: Deep Seek, 通义千问(Qwen), 智谱AI(GLM), OpenAI(ChatGPT), Claude
    """

    # 平台配置映射
    PLATFORM_CONFIGS = {
        "deepseek": {
            "name": "Deep Seek",
            "default_base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
            "supports_streaming": True,
            "auth_type": "bearer"  # API Key认证
        },
        "qwen": {
            "name": "通义千问 (阿里云百炼)",
            "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen-plus",
            "supports_streaming": True,
            "auth_type": "bearer"  # API Key认证
        },
        "zhipu": {
            "name": "智谱AI (GLM)",
            "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
            "default_model": "glm-4-flash",
            "supports_streaming": True,
            "auth_type": "bearer"  # API Key认证
        },
        "openai": {
            "name": "OpenAI (ChatGPT)",
            "default_base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
            "supports_streaming": True,
            "auth_type": "bearer"  # API Key认证
        },
        "claude": {
            "name": "Anthropic (Claude)",
            "default_base_url": "https://api.anthropic.com/v1",
            "default_model": "claude-3-5-haiku-20241022",
            "supports_streaming": True,
            "auth_type": "anthropic",  # 特殊认证头
            "endpoint": "/messages"  # Claude使用不同的端点
        }
    }

    def __init__(
        self,
        platform: str,
        api_key: str,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120,
        max_retries: int = 3
    ):
        """
        初始化云端AI客户端

        Args:
            platform: 平台类型 (deepseek, qwen, zhipu, openai, claude)
            api_key: API密钥
            base_url: API基础URL（可选，使用默认值）
            model: 模型名称（可选，使用默认值）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.platform = platform.lower()
        
        if self.platform not in self.PLATFORM_CONFIGS:
            raise ValueError(f"不支持的平台: {platform}。支持的平台: {list(self.PLATFORM_CONFIGS.keys())}")
        
        platform_config = self.PLATFORM_CONFIGS[self.platform]
        
        self.base_url = (base_url or platform_config["default_base_url"]).rstrip('/')
        self.model = model or platform_config["default_model"]
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.platform_config = platform_config
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._is_connected = False

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        if self.platform_config["auth_type"] == "bearer":
            return {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        elif self.platform_config["auth_type"] == "anthropic":
            return {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "anthropic-dangerous-direct-browser-access": "true"
            }
        return {"Content-Type": "application/json"}

    async def _make_request(self, payload: Dict[str, Any], stream: bool = False) -> Dict[str, Any]:
        """发送请求到云端AI API"""
        session = await self._get_session()
        headers = self._get_headers()
        
        # Claude使用不同的API端点
        if self.platform == "claude":
            endpoint = self.platform_config.get("endpoint", "/messages")
        else:
            endpoint = "/chat/completions"
        
        url = f"{self.base_url}{endpoint}"
        
        # Claude API格式不同
        if self.platform == "claude":
            # 转换消息格式
            messages = payload.pop("messages", [])
            payload["model"] = self.model
            payload["messages"] = messages
            if "max_tokens" not in payload:
                payload["max_tokens"] = 1024
        
        payload["model"] = self.model
        payload["stream"] = stream
        
        logger.debug(f"Sending request to {self.platform}: {url}")
        logger.debug(f"Model: {self.model}")
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with session.post(url, json=payload, headers=headers) as response:
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
                                        if self.platform == "claude":
                                            # Claude流式响应格式
                                            if "delta" in data:
                                                result.append(data["delta"].get("text", ""))
                                        else:
                                            if "choices" in data and len(data["choices"]) > 0:
                                                delta = data["choices"][0].get("delta", {})
                                                if "content" in delta:
                                                    result.append(delta["content"])
                                    except json.JSONDecodeError:
                                        continue
                        return {"content": "".join(result)}
                    else:
                        data = await response.json()
                        
                        if self.platform == "claude":
                            if "content" in data and len(data["content"]) > 0:
                                return {"content": data["content"][0].get("text", "")}
                            return {"content": ""}
                        else:
                            if "choices" in data and len(data["choices"]) > 0:
                                return {"content": data["choices"][0].get("message", {}).get("content", "")}
                            return {"content": ""}

            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries}")
                await asyncio.sleep(2 ** attempt)

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Client error on attempt {attempt + 1}/{self.max_retries}: {e}")
                await asyncio.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise RuntimeError(f"Failed to communicate with {self.platform}: {e}")

        raise RuntimeError(f"Max retries ({self.max_retries}) exceeded. Last error: {last_error}")

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        stream: bool = False
    ) -> str:
        """
        调用云端AI生成文本

        Args:
            prompt: 提示词
            system: 系统提示词
            temperature: 温度参数（0-1，越低越确定）
            max_tokens: 最大生成长度
            stream: 是否流式返回

        Returns:
            生成的文本
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        logger.debug(f"Generating text with {self.platform}, prompt length: {len(prompt)}")

        result = await self._make_request(payload, stream)
        return result.get("content", "")

    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文本

        Args:
            prompt: 提示词
            system: 系统提示词
            temperature: 温度参数
            max_tokens: 最大生成长度

        Yields:
            生成的文本片段
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        session = await self._get_session()
        headers = self._get_headers()
        
        if self.platform == "claude":
            endpoint = self.platform_config.get("endpoint", "/messages")
        else:
            endpoint = "/chat/completions"
        
        url = f"{self.base_url}{endpoint}"
        
        if self.platform == "claude":
            payload["model"] = self.model
            payload["stream"] = True
            payload["messages"] = messages
        else:
            payload["model"] = self.model
            payload["stream"] = True

        try:
            async with session.post(url, json=payload, headers=headers) as response:
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
                                if self.platform == "claude":
                                    if "delta" in data:
                                        text = data["delta"].get("text", "")
                                        if text:
                                            yield text
                                else:
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
        max_tokens: int = 2048
    ) -> str:
        """
        聊天模式（支持多轮对话）

        Args:
            messages: 消息列表，格式：[{"role": "user", "content": "..."}, ...]
            temperature: 温度参数
            max_tokens: 最大生成长度

        Returns:
            助手回复
        """
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        result = await self._make_request(payload)
        return result.get("content", "")

    async def test_connection(self) -> bool:
        """
        测试云端AI连接

        Returns:
            是否连接成功
        """
        try:
            # 发送一个简单的测试请求
            test_payload = {
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10
            }

            if self.platform == "claude":
                test_payload["model"] = self.model

            session = await self._get_session()
            headers = self._get_headers()
            
            if self.platform == "claude":
                endpoint = self.platform_config.get("endpoint", "/messages")
            else:
                endpoint = "/chat/completions"
            
            url = f"{self.base_url}{endpoint}"

            async with session.post(url, json=test_payload, headers=headers) as response:
                response.raise_for_status()
                logger.info(f"{self.platform_config['name']} connection successful, model: {self.model}")
                self._is_connected = True
                return True

        except aiohttp.ClientError as e:
            logger.error(f"Failed to test {self.platform} connection: {e}")
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
        return {
            "platform": self.platform,
            "platform_name": self.platform_config["name"],
            "model": self.model,
            "base_url": self.base_url
        }

    async def list_models(self) -> list[str]:
        """
        列出可用模型（云端通常通过不同接口获取）

        Returns:
            模型名称列表
        """
        # 云端平台通常不需要列出模型，返回当前模型
        return [self.model]

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._is_connected

    @property
    def platform_name(self) -> str:
        """获取平台显示名称"""
        return self.platform_config["name"]

    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info(f"{self.platform} client session closed")


# 便捷函数：根据配置创建云端AI客户端
def create_cloud_client(
    platform: str,
    api_key: str,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 120,
    max_retries: int = 3
) -> CloudAIClient:
    """
    创建云端AI客户端的便捷函数

    Args:
        platform: 平台类型
        api_key: API密钥
        base_url: API基础URL
        model: 模型名称
        timeout: 超时时间
        max_retries: 最大重试次数

    Returns:
        CloudAIClient实例
    """
    return CloudAIClient(
        platform=platform,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        max_retries=max_retries
    )
