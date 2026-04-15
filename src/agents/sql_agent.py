"""SQL生成Agent - 基于LangChain ReAct"""
import json
import logging
from typing import Dict, Any, Optional, List, Sequence
from datetime import datetime
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import BaseTool

from ..database.prompts import PromptManager
from ..database.schema import SchemaManager
from ..security.validator import SQLValidator

logger = logging.getLogger(__name__)


class SQLAgent:
    """
    SQL生成Agent - 基于LangChain ReAct模式

    核心特性：
    1. 工具调用完全由LLM自主决定
    2. 所有提示词从配置文件动态加载
    3. 支持多轮对话和上下文记忆
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Sequence[BaseTool],
        schema_manager: SchemaManager,
        prompt_manager: PromptManager,
        sql_validator: SQLValidator,
        max_iterations: int = 10
    ):
        """
        初始化SQL Agent

        Args:
            llm: LangChain兼容的聊天模型
            tools: 可用工具列表
            schema_manager: Schema管理器
            prompt_manager: 提示词管理器
            sql_validator: SQL验证器
            max_iterations: 最大迭代次数
        """
        self.llm = llm
        self.tools = list(tools)
        self.tool_map = {tool.name: tool for tool in tools}
        self.schema_manager = schema_manager
        self.prompt_manager = prompt_manager
        self.sql_validator = sql_validator
        self.max_iterations = max_iterations

        # 创建绑定工具的LLM
        self.bound_llm = llm.bind_tools(tools)

        # 记忆系统
        self.conversation_history: List[Dict] = []
        self.memory: List[Dict] = []

        # 构建系统提示词
        self.system_prompt = self._build_system_prompt()

        logger.info(f"SQLAgent初始化完成，工具数量: {len(tools)}")

    def _build_system_prompt(self) -> str:
        """构建系统提示词 - 从配置文件加载"""
        # 使用完整Schema格式（包含字段列表），而不是只有摘要
        schema_text = self.schema_manager.format_schema_for_prompt()

        # 传递schema_manager以自动生成字段映射规则
        prompt = self.prompt_manager.build_agent_system_prompt(
            schema_summary=schema_text,
            schema_manager=self.schema_manager
        )

        logger.info(f"SQLAgent系统提示词长度: {len(prompt)} 字符")

        return prompt

    def add_to_history(self, role: str, content: str):
        """添加对话历史"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

    def get_history(self, max_entries: int = 10) -> List[Dict]:
        """获取对话历史"""
        return self.conversation_history[-max_entries:]

    def add_memory(self, content: str, metadata: Dict = None):
        """添加记忆"""
        self.memory.append({
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "metadata": metadata or {}
        })

    def get_memory(self, max_entries: int = 10) -> List[Dict]:
        """获取记忆"""
        return self.memory[-max_entries:]

    async def ainvoke(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        异步调用Agent处理查询

        Args:
            query: 用户自然语言查询
            user_context: 用户上下文信息

        Returns:
            Agent执行结果
        """
        logger.info(f"Agent处理查询: {query}")

        # 添加用户查询到历史
        self.add_to_history("user", query)

        # 构建消息列表
        messages = [SystemMessage(content=self.system_prompt)]

        # 添加历史对话
        for msg in self.get_history(max_entries=5):
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

        # 添加当前查询
        messages.append(HumanMessage(content=query))

        # 执行ReAct循环
        try:
            result = await self._execute_agent_loop(messages, query)
            self.add_to_history("assistant", str(result))
            return result
        except Exception as e:
            logger.error(f"Agent执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

    async def _execute_agent_loop(
        self,
        messages: List,
        original_query: str
    ) -> Dict[str, Any]:
        """执行Agent循环 - 工具调用由LLM自主决定"""
        intermediate_steps = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.debug(f"Agent迭代 {iteration}/{self.max_iterations}")

            # 调用LLM
            response = await self.bound_llm.ainvoke(messages)

            # 获取LLM响应
            ai_message = response.content if hasattr(response, 'content') else str(response)
            messages.append(AIMessage(content=ai_message))

            # 检查是否有工具调用
            tool_calls = []
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_calls = response.tool_calls
            elif hasattr(response, 'additional_kwargs'):
                tool_calls = response.additional_kwargs.get('tool_calls', [])

            if not tool_calls:
                # 没有更多工具调用，返回最终结果
                return self._parse_final_response(ai_message, intermediate_steps)

            # 执行工具调用
            for tool_call in tool_calls:
                tool_name = tool_call.get('name') or tool_call.get('function', {}).get('name')
                tool_args = tool_call.get('arguments') or tool_call.get('function', {}).get('arguments', {})

                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                logger.info(f"执行工具: {tool_name}, 参数: {tool_args}")

                # 获取工具并执行
                tool = self.tool_map.get(tool_name)
                if not tool:
                    tool_result = f"工具 {tool_name} 不存在"
                    logger.warning(tool_result)
                else:
                    try:
                        # 根据工具是否为异步执行
                        if hasattr(tool, '_arun'):
                            tool_result = await tool._arun(**tool_args)
                        else:
                            tool_result = tool._run(**tool_args)
                    except Exception as e:
                        tool_result = f"工具执行失败: {str(e)}"
                        logger.error(tool_result)

                # 添加工具结果到消息
                from langchain_core.messages import ToolMessage
                tool_message = ToolMessage(
                    content=str(tool_result),
                    tool_call_id=str(tool_call.get('id', 'unknown'))
                )
                messages.append(tool_message)

                # 记录中间步骤
                intermediate_steps.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": str(tool_result)[:500]  # 截断长结果
                })

        # 达到最大迭代次数
        return {
            "success": False,
            "error": f"达到最大迭代次数 ({self.max_iterations})",
            "intermediate_steps": intermediate_steps
        }

    def _normalize_python_json(self, text: str) -> str:
        """将Python风格JSON转为标准JSON"""
        import re
        import ast

        # 先尝试用 ast.literal_eval 解析 Python dict
        try:
            data = ast.literal_eval(text)
            import json as json_mod
            return json_mod.dumps(data, ensure_ascii=False)
        except (ValueError, SyntaxError):
            pass

        # 回退：手动替换
        text = text.replace("'", '"')
        text = text.replace('True', 'true').replace('False', 'false').replace('None', 'null')
        return text

    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """
        从文本中提取JSON字符串
        """
        if not text:
            return None

        text = text.strip()

        # 格式1: 直接以{开头
        if text.startswith('{'):
            brace_count = 0
            for i, char in enumerate(text):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = text[:i+1]
                        # 尝试解析，失败则尝试标准化
                        try:
                            json.loads(json_str)
                            return json_str
                        except json.JSONDecodeError:
                            normalized = self._normalize_python_json(json_str)
                            try:
                                json.loads(normalized)
                                return normalized
                            except json.JSONDecodeError:
                                return json_str

        # 格式2: Markdown代码块
        import re
        patterns = [
            r'```json\s*\n?(.*?)\n?```',
            r'```\s*\n?(.*?)\n?```',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                if json_str.startswith('{'):
                    try:
                        json.loads(json_str)
                        return json_str
                    except json.JSONDecodeError:
                        normalized = self._normalize_python_json(json_str)
                        try:
                            json.loads(normalized)
                            return normalized
                        except json.JSONDecodeError:
                            return json_str

        return None

    def _parse_final_response(self, response: str, intermediate_steps: List) -> Dict[str, Any]:
        """解析最终响应"""
        json_str = self._extract_json_from_text(response)

        if json_str:
            try:
                data = json.loads(json_str)
                # 深度提取：如果response字段包含实际的JSON结果（嵌套结构），提取出来
                if isinstance(data, dict) and "response" in data:
                    inner = data["response"]
                    if isinstance(inner, str):
                        try:
                            inner_data = json.loads(inner)
                            data = inner_data  # 用内部数据替换
                        except json.JSONDecodeError:
                            pass  # 保持原样
                    elif isinstance(inner, dict):
                        # response 已经是 dict，直接用
                        data = inner
                
                # 提取SQL用于日志
                sql = data.get("sql") if isinstance(data, dict) else None
                logger.info(f"生成的SQL: {sql}")
                
                return {
                    "success": True,
                    "response": data,
                    "intermediate_steps": intermediate_steps
                }
            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {e}, 原始响应: {response[:500]}")

        # 无法解析JSON
        logger.warning(f"无法解析JSON响应: {response[:500]}...")
        return {
            "success": True,
            "response": response,
            "intermediate_steps": intermediate_steps
        }

    def invoke(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """同步调用Agent"""
        import asyncio
        return asyncio.run(self.ainvoke(query, user_context))

    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        return {
            "initialized": True,
            "tools_count": len(self.tools),
            "available_tools": [t.name for t in self.tools],
            "conversation_count": len(self.conversation_history),
            "memory_entries": len(self.memory)
        }
