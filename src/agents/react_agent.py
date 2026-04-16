"""ReAct Agent - LangChain v1.0 标准实现

核心设计原则：
1. 零硬编码：所有提示词、业务逻辑从配置加载
2. LLM自主决策：工具调用顺序由LLM决定
3. 单一职责：代码只负责工具执行
"""
import json
import logging
from typing import Dict, Any, Optional, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class ReActAgent:
    """
    ReAct Agent - 支持工具链调用的通用Agent

    职责：
    1. 维护工具集合
    2. 执行LLM决定的工具调用
    3. 管理对话上下文
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: List[BaseTool],
        system_prompt: Optional[str] = None,
        max_iterations: int = 10
    ):
        self.llm = llm
        self.tools = tools
        self.tools_dict = {tool.name: tool for tool in tools}
        self.system_prompt = system_prompt or ""
        self.max_iterations = max_iterations

    async def ainvoke(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        异步调用Agent

        流程：
        1. 构建系统提示词（从配置加载）
        2. 循环调用LLM，直到LLM输出最终结果
        3. 如果LLM请求工具调用，执行工具并继续循环
        4. 返回最终结果
        """
        logger.info(f"Agent处理查询: {query}")

        try:
            messages = []
            if self.system_prompt:
                messages.append(SystemMessage(content=self.system_prompt))
            messages.append(HumanMessage(content=query))

            llm_with_tools = self.llm.bind_tools(self.tools)

            iteration = 0
            execution_log = []

            while iteration < self.max_iterations:
                iteration += 1
                logger.debug(f"Agent迭代 {iteration}")

                response = await llm_with_tools.ainvoke(messages)

                if hasattr(response, 'tool_calls') and response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_name = tool_call.get('name')
                        tool_args = tool_call.get('args', {})
                        tool_id = tool_call.get('id', '')

                        logger.info(f"工具调用: {tool_name}({tool_args})")

                        if tool_name in self.tools_dict:
                            try:
                                result = await self.tools_dict[tool_name].ainvoke(tool_args)
                                execution_log.append({
                                    "tool": tool_name,
                                    "args": tool_args,
                                    "result": result
                                })

                                messages.append(AIMessage(content="", tool_calls=[tool_call]))
                                messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))
                            except Exception as e:
                                logger.error(f"工具执行失败 {tool_name}: {e}")
                                messages.append(ToolMessage(content=json.dumps({"error": str(e)}), tool_call_id=tool_id))
                        else:
                            logger.warning(f"未知工具: {tool_name}")
                            messages.append(ToolMessage(content=json.dumps({"error": f"未知工具: {tool_name}"}), tool_call_id=tool_id))

                    continue

                final_content = response.content if hasattr(response, 'content') else str(response)

                return {
                    "success": True,
                    "result": final_content,
                    "execution_log": execution_log,
                    "iterations": iteration,
                    "query": query
                }

            logger.warning(f"达到最大迭代次数: {self.max_iterations}")
            return {
                "success": False,
                "error": "达到最大迭代次数限制",
                "execution_log": execution_log,
                "query": query
            }

        except Exception as e:
            logger.error(f"Agent执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

    def invoke(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """同步调用Agent"""
        import asyncio
        return asyncio.run(self.ainvoke(query, context))


def create_react_agent(
    llm: BaseChatModel,
    tools: List[BaseTool],
    system_prompt: Optional[str] = None,
    max_iterations: int = 10
) -> ReActAgent:
    """创建ReAct Agent实例"""
    logger.info(f"创建ReAct Agent，工具: {[t.name for t in tools]}")
    return ReActAgent(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
        max_iterations=max_iterations
    )
