"""LangChain ChatModel适配器 - 简化版"""
import json
import logging
import re
from typing import Any, Dict, List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun
from pydantic import ConfigDict, Field

logger = logging.getLogger(__name__)


class ChatModelAdapter(BaseChatModel):
    """
    LangChain ChatModel 适配器 - 简化版
    将AI客户端适配为LangChain兼容的接口
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ai_client: Any = Field(default=None, description="AI客户端实例")
    model_name: str = Field(default="custom", description="模型名称")

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        """同步生成响应"""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._agenerate(messages, stop, **kwargs))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"生成失败: {e}")
            return ChatResult(
                generations=[ChatGeneration(
                    message=AIMessage(content=f"Error: {str(e)}"),
                    generation_info={"error": str(e)}
                )]
            )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any
    ) -> ChatResult:
        """异步生成响应"""
        try:
            # 分离系统消息和用户消息
            system_message = ""
            user_messages = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    user_messages.append(msg.content)
                elif isinstance(msg, SystemMessage):
                    system_message = msg.content

            # 构建用户消息内容
            user_content = "\n\n".join(user_messages)

            # 调用AI客户端
            response = await self.ai_client.generate(
                prompt=user_content,
                system=system_message,
                temperature=kwargs.get("temperature", 0.7)
            )

            # 解析响应
            content = self._get_content_from_response(response)

            return ChatResult(
                generations=[ChatGeneration(
                    message=AIMessage(content=content),
                    generation_info={"raw_response": response}
                )]
            )

        except Exception as e:
            logger.error(f"异步生成失败: {e}")
            return ChatResult(
                generations=[ChatGeneration(
                    message=AIMessage(content=f"Error: {str(e)}"),
                    generation_info={"error": str(e)}
                )]
            )

    def _get_content_from_response(self, response: Any) -> str:
        """从响应中提取文本内容"""
        if isinstance(response, str):
            return response
        elif isinstance(response, dict):
            return str(response.get("content", json.dumps(response)))
        elif hasattr(response, 'content'):
            return str(response.content)
        else:
            return str(response)

    @property
    def _llm_type(self) -> str:
        return self.model_name or "custom_ai"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "base_url": getattr(self.ai_client, 'base_url', None)
        }
