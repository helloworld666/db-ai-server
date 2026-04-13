"""
LangChain LLM 适配器
将现有的 AI 客户端适配为 LangChain 兼容的 LLM 接口
"""

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
    将 Ollama/LMStudio/CloudAI 客户端适配为 LangChain 兼容的接口
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
        """
        同步生成响应

        Args:
            messages: 消息列表
            stop: 停止词列表
            run_manager: 回调管理器
            **kwargs: 其他参数

        Returns:
            ChatResult: 聊天结果
        """
        import asyncio

        try:
            # 创建独立的新事件循环，避免与现有事件循环冲突
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._agenerate(messages, stop, **kwargs))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"生成失败: {e}")
            # 返回错误响应
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
        """
        异步生成响应
        """
        try:
            # 检查是否绑定了工具
            has_tools = hasattr(self, '_tool_schemas') and self._tool_schemas
            
            # 分离系统消息和用户消息
            system_message = ""
            user_messages = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    user_messages.append(msg.content)
                elif isinstance(msg, AIMessage):
                    user_messages.append(f"助手: {msg.content}")
                elif isinstance(msg, SystemMessage):
                    system_message = msg.content

            # 构建用户消息内容
            user_content = "\n\n".join([f"用户: {content}" for content in user_messages])
            
            # 如果绑定了工具，添加工具定义
            if has_tools:
                tool_section = "\n\n## 可用工具\n你必须根据用户需求选择调用以下工具。直接回复工具调用的JSON：\n\n"
                for schema in self._tool_schemas:
                    name = schema.get('name', 'unknown')
                    desc = schema.get('description', '')
                    params = schema.get('parameters', {})
                    props = params.get('properties', {})
                    required = params.get('required', [])
                    
                    tool_section += f"### {name}\n"
                    tool_section += f"{desc}\n"
                    if props:
                        tool_section += "参数:\n"
                        for pname, pinfo in props.items():
                            ptype = pinfo.get('type', 'string')
                            pdesc = pinfo.get('description', '')
                            required_mark = "(必需)" if pname in required else "(可选)"
                            tool_section += f"  - {pname}: {ptype} {required_mark} - {pdesc}\n"
                    tool_section += "\n"
                
                tool_section += "**重要规则**\n"
                tool_section += "1. 调用工具时必须包含 arguments 字段，如果没有参数则写 {}，禁止只写工具名\n"
                tool_section += "2. 正确格式：```json\n{\"name\": \"工具名\", \"arguments\": {}}\n```\n"
                tool_section += "3. 错误格式：{\"name\": \"工具名\"} - 缺少 arguments\n"
                
                user_content += tool_section
            
            # 调用 AI 客户端，传递工具信息
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

            # 尝试从响应中提取工具调用
            import json
            from langchain_core.messages import ToolMessage

            # 检查响应是否包含工具调用
            tool_calls = []
            if has_tools:
                # 尝试从 JSON 中提取工具调用
                try:
                    # 移除代码块标记
                    if content.startswith("```json") and content.endswith("```"):
                        content = content[7:-3].strip()
                    # 解析 JSON
                    tool_call_data = json.loads(content)
                    if isinstance(tool_call_data, dict) and "name" in tool_call_data:
                        # 构建工具调用，使用正确的格式
                        from langchain_core.messages import ToolCall
                        tool_call = ToolCall(
                            name=tool_call_data["name"],
                            args=tool_call_data.get("arguments", {}),
                            id="1"  # 添加 id 参数
                        )
                        tool_calls.append(tool_call)
                except json.JSONDecodeError:
                    # 不是有效的 JSON，继续处理
                    pass

            # 如果有工具调用，返回 AIMessage 带工具调用
            if tool_calls:
                # 构建工具调用消息
                tool_call_message = AIMessage(
                    content=content,
                    tool_calls=tool_calls
                )
                return ChatResult(
                    generations=[ChatGeneration(
                        message=tool_call_message,
                        generation_info={"raw_response": response, "has_tools": has_tools, "tool_calls": tool_calls}
                    )]
                )
            else:
                # 没有工具调用，返回普通消息
                return ChatResult(
                    generations=[ChatGeneration(
                        message=AIMessage(content=content),
                        generation_info={"raw_response": response, "has_tools": has_tools}
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

    def _format_messages(self, messages: List[Dict[str, str]], include_tools: bool = False) -> str:
        """
        将消息列表格式化为提示词字符串

        Args:
            messages: 消息列表
            include_tools: 是否包含工具定义

        Returns:
            格式化的提示词
        """
        formatted = []
        tool_section = ""

        # 如果绑定了工具，添加工具定义
        if include_tools and hasattr(self, '_tool_schemas') and self._tool_schemas:
            tool_section = "\n\n## 可用工具\n你必须根据用户需求选择调用以下工具。直接回复工具调用的JSON：\n\n"
            for schema in self._tool_schemas:
                name = schema.get('name', 'unknown')
                desc = schema.get('description', '')
                params = schema.get('parameters', {})
                props = params.get('properties', {})
                required = params.get('required', [])
                
                tool_section += f"### {name}\n"
                tool_section += f"{desc}\n"
                if props:
                    tool_section += "参数:\n"
                    for pname, pinfo in props.items():
                        ptype = pinfo.get('type', 'string')
                        pdesc = pinfo.get('description', '')
                        required_mark = "(必需)" if pname in required else "(可选)"
                        tool_section += f"  - {pname}: {ptype} {required_mark} - {pdesc}\n"
                tool_section += "\n"
            
            tool_section += "**重要规则**\n"
            tool_section += "1. 调用工具时必须包含 arguments 字段，如果没有参数则写 {}，禁止只写工具名\n"
            tool_section += "2. 正确格式：```json\n{\"name\": \"工具名\", \"arguments\": {}}\n```\n"
            tool_section += "3. 错误格式：{\"name\": \"工具名\"} - 缺少 arguments\n"

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                formatted.append(f"系统: {content}{tool_section}")
            elif role == "user":
                formatted.append(f"用户: {content}")
            elif role == "assistant":
                formatted.append(f"助手: {content}")

        return "\n\n".join(formatted)

    @property
    def _llm_type(self) -> str:
        """返回 LLM 类型"""
        return self.model_name or "custom_ai"

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> "ChatModelAdapter":
        """
        绑定工具到 LLM
        对于自定义 LLM，返回一个绑定工具的适配器

        Args:
            tools: LangChain 工具列表
            **kwargs: 其他参数

        Returns:
            绑定工具的模型实例
        """
        from langchain_core.utils.function_calling import convert_to_openai_function

        # 创建绑定工具的适配器
        bound_adapter = ChatModelAdapter(
            ai_client=self.ai_client,
            model_name=self.model_name
        )
        bound_adapter._bound_tools = tools
        # 转换为 OpenAI 函数格式
        bound_adapter._tool_schemas = [convert_to_openai_function(tool) for tool in tools]
        return bound_adapter

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """返回标识参数"""
        return {
            "model_name": self.model_name,
            "base_url": getattr(self.ai_client, 'base_url', None)
        }

    def __init__(
        self,
        ai_client=None,
        model_name: str = "custom",
        **kwargs
    ):
        """
        初始化适配器

        Args:
            ai_client: AI 客户端实例 (OllamaClient/LMStudioClient/CloudAIClient)
            model_name: 模型名称
            **kwargs: 其他参数
        """
        super().__init__(ai_client=ai_client, model_name=model_name, **kwargs)


class OllamaLLMAdapter(ChatModelAdapter):
    """Ollama 专用适配器"""

    def __init__(self, base_url: str, model: str, **kwargs):
        from src.ollama_client import OllamaClient
        ai_client = OllamaClient(base_url=base_url, model=model)
        super().__init__(ai_client=ai_client, model_name=f"ollama_{model}", **kwargs)


class LMStudioLLMAdapter(ChatModelAdapter):
    """LM Studio 专用适配器"""

    def __init__(self, base_url: str, model: str, **kwargs):
        from src.lmstudio_client import LMStudioClient
        ai_client = LMStudioClient(base_url=base_url, model=model)
        super().__init__(ai_client=ai_client, model_name=f"lmstudio_{model}", **kwargs)


class CloudAILLMAdapter(ChatModelAdapter):
    """云端 AI 平台专用适配器"""

    def __init__(self, platform: str, api_key: str, base_url: str, model: str, **kwargs):
        from src.cloud_ai_client import CloudAIClient
        ai_client = CloudAIClient(
            platform=platform,
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        super().__init__(ai_client=ai_client, model_name=f"{platform}_{model}", **kwargs)


def create_llm_adapter(
    engine_type: str,
    config: Dict[str, Any],
    existing_client=None
) -> ChatModelAdapter:
    """
    根据配置创建合适的 LLM 适配器

    Args:
        engine_type: 引擎类型 (ollama/lmstudio/deepseek/qwen等)
        config: 引擎配置
        existing_client: 可选，已有 AI 客户端实例

    Returns:
        ChatModelAdapter: LLM 适配器实例
    """
    base_url = config.get("base_url")
    model = config.get("model")

    # 如果提供了已有客户端，复用它
    if existing_client is not None:
        return ChatModelAdapter(
            ai_client=existing_client,
            model_name=f"{engine_type}_{model}"
        )

    cloud_platforms = ['deepseek', 'qwen', 'zhipu', 'openai', 'claude']

    if engine_type in cloud_platforms:
        return CloudAILLMAdapter(
            platform=engine_type,
            api_key=config.get("api_key", ""),
            base_url=base_url,
            model=model
        )
    elif engine_type == "lmstudio":
        return LMStudioLLMAdapter(
            base_url=base_url,
            model=model
        )
    else:  # 默认使用 Ollama
        return OllamaLLMAdapter(
            base_url=base_url,
            model=model
        )
