"""
LangChain Agent 实现
使用 LangGraph 工作流
"""

import json
import logging
from typing import Dict, Any, List, Optional, Sequence
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.langgraph_workflow import DatabaseWorkflow
from src.database_connector import DatabaseConnector
from src.schema_manager import SchemaManager

logger = logging.getLogger(__name__)


class DatabaseAgent:
    """
    基于 LangGraph 工作流的数据库智能代理
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Sequence[BaseTool],
        config_loader,
        system_prompt: Optional[str] = None
    ):
        """
        初始化 Agent
        """
        self.llm = llm
        self.tools = list(tools)
        self.config_loader = config_loader
        self.tool_map = {tool.name: tool for tool in tools}

        # 构建系统提示词
        self.system_message = system_prompt or self._build_system_prompt()

        # 初始化数据库连接器和 schema 管理器
        db_config = config_loader.get('server.database.connection_string')
        self.db_connector = DatabaseConnector(db_config)
        self.schema_manager = SchemaManager(db_config)

        # 导入验证和评估函数
        from src.mcp_server import _validate_sql, _evaluate_risk, _generate_suggestions, _parse_ai_response, _build_sql_prompt

        # 初始化 LangGraph 工作流
        self.workflow = DatabaseWorkflow(
            llm=self.llm,
            tools=self.tools,
            config_loader=self.config_loader,
            validate_sql_func=_validate_sql,
            evaluate_risk_func=_evaluate_risk
        )

        logger.info(f"DatabaseAgent 初始化完成，共 {len(tools)} 个工具")

        self.conversation_history: List[Dict] = []
        self.memory: List[Dict] = []

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        prompts_config = self.config_loader.get_prompts_config()

        # 只使用系统提示词，不添加额外规则，避免系统提示词太长
        return prompts_config.get('system_prompt', '')

    def add_memory(self, content: str, metadata: Dict = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "metadata": metadata or {}
        }
        self.memory.append(entry)

    def get_memory_summary(self, max_entries: int = 10) -> List[Dict]:
        return self.memory[-max_entries:] if len(self.memory) > max_entries else self.memory

    async def ainvoke(self, query: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """异步调用 Agent"""
        logger.info(f"Agent 处理请求: {query}")

        try:
            # 使用 LangGraph 工作流，通过 LM Studio 生成 SQL
            result = await self.workflow.ainvoke(query, user_context)
            # 解析工作流结果
            if result.get("success"):
                # 构建响应
                response = result.get("response", "")

                self.conversation_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "query": query,
                    "response": response,
                    "steps": len(result.get("steps", []))
                })

                # 尝试从响应中提取执行结果
                execution_result = None
                rows = []
                row_count = 0
                columns = []
                column_comments = {}

                try:
                    if isinstance(response, str):
                        response_data = json.loads(response)
                        execution_result = response_data.get("execution_result")
                        if execution_result:
                            rows = execution_result.get("rows", [])
                            row_count = len(rows)
                            columns = execution_result.get("columns", [])
                            column_comments = execution_result.get("column_comments", {})
                except json.JSONDecodeError:
                    pass

                # 构建返回结果
                return {
                    "success": True,
                    "query": query,
                    "response": response,
                    "intermediate_steps": result.get("steps", []),
                    "memory_summary": self.get_memory_summary(5),
                    "rows": rows,
                    "row_count": row_count,
                    "columns": columns,
                    "column_comments": column_comments
                }
            else:
                return {
                    "success": False,
                    "query": query,
                    "error": result.get("error", "工作流执行失败")
                }

        except Exception as e:
            logger.error(f"Agent 执行失败: {e}", exc_info=True)
            return {
                "success": False,
                "query": query,
                "error": str(e)
            }

    def invoke(self, query: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """同步调用 Agent"""
        import asyncio
        return asyncio.run(self.ainvoke(query, user_context))

    def get_tools_description(self) -> List[Dict]:
        return [{"name": tool.name, "description": tool.description} for tool in self.tools]

    def get_status(self) -> Dict[str, Any]:
        return {
            "initialized": True,
            "tools_count": len(self.tools),
            "conversation_count": len(self.conversation_history),
            "memory_entries": len(self.memory),
            "available_tools": [t.name for t in self.tools]
        }
