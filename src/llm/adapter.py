"""LangChain ChatModel适配器"""
import json
import logging
from typing import Any, Dict, List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun
from pydantic import ConfigDict, Field

logger = logging.getLogger(__name__)


class ChatModelAdapter(BaseChatModel):
    """
    LangChain ChatModel 适配器
    将各种AI客户端适配为LangChain兼容的接口
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ai_client: Any = Field(default=None, description="AI客户端实例")
    model_name: str = Field(default="custom", description="模型名称")
    bound_tools: List[Any] = Field(default_factory=list, exclude=True)
    tool_schemas: List[Dict] = Field(default_factory=list, exclude=True)

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
            has_tools = bool(self.tool_schemas)

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

            # 如果绑定了工具，添加工具定义
            if has_tools:
                tool_section = self._build_tool_section()
                user_content += tool_section

            # 调用AI客户端
            response = await self.ai_client.generate(
                prompt=user_content,
                system=system_message,
                temperature=kwargs.get("temperature", 0.7)
            )

            # 解析响应
            if isinstance(response, str):
                content = response
            elif isinstance(response, dict):
                content = response.get("content", str(response))
            else:
                content = str(response)

            # 尝试解析工具调用
            tool_calls = []
            if has_tools:
                tool_calls = self._parse_tool_calls(content)

            if tool_calls:
                from langchain_core.messages import ToolCall
                tool_call_message = AIMessage(
                    content=content,
                    tool_calls=[ToolCall(
                        name=tc["name"],
                        args=tc.get("arguments", {}),
                        id=str(i)
                    ) for i, tc in enumerate(tool_calls)]
                )
                return ChatResult(
                    generations=[ChatGeneration(
                        message=tool_call_message,
                        generation_info={"raw_response": response, "has_tools": True}
                    )]
                )
            else:
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

    def _build_tool_section(self) -> str:
        """构建工具定义部分"""
        if not self.tool_schemas:
            return ""

        section = "\n\n## 可用工具\n根据用户需求选择调用以下工具：\n\n"
        for schema in self._tool_schemas:
            name = schema.get('function', {}).get('name', schema.get('name', 'unknown'))
            desc = schema.get('function', {}).get('description', schema.get('description', ''))
            params = schema.get('function', {}).get('parameters', {})
            props = params.get('properties', {})
            required = params.get('required', [])

            section += f"### {name}\n"
            section += f"{desc}\n"
            if props:
                section += "参数:\n"
                for pname, pinfo in props.items():
                    ptype = pinfo.get('type', 'string')
                    pdesc = pinfo.get('description', '')
                    required_mark = "(必需)" if pname in required else "(可选)"
                    section += f"  - {pname}: {ptype} {required_mark} - {pdesc}\n"
            section += "\n"

        section += "**重要**: 调用工具时使用JSON格式，包含name和arguments字段\n"
        return section

    def _parse_tool_calls(self, content: str) -> List[Dict]:
        """解析工具调用"""
        try:
            # 尝试从JSON中提取工具调用
            if content.strip().startswith("{"):
                data = json.loads(content)
                if "name" in data:
                    return [data]
            elif content.strip().startswith("["):
                return json.loads(content)
        except json.JSONDecodeError:
            pass
        return []

    @property
    def _llm_type(self) -> str:
        return self.model_name or "custom_ai"

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> "ChatModelAdapter":
        """绑定工具到LLM"""
        from langchain_core.utils.function_calling import convert_to_openai_function

        bound_adapter = ChatModelAdapter(
            ai_client=self.ai_client,
            model_name=self.model_name
        )
        bound_adapter.bound_tools = tools
        bound_adapter.tool_schemas = [convert_to_openai_function(tool) for tool in tools]
        return bound_adapter

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "base_url": getattr(self.ai_client, 'base_url', None)
        }
