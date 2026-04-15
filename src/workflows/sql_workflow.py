"""SQL工作流 - 基于LangGraph"""
import json
import logging
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.graph import MessagesState as LangGraphMessagesState
from langchain_core.messages import HumanMessage, SystemMessage

from ..core.types import AgentState
from ..database.connection import DatabaseConnection
from ..database.schema import SchemaManager
from ..database.prompts import PromptManager
from ..security.validator import SQLValidator

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """操作类型"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    UNKNOWN = "unknown"


class SQLWorkflow:
    """
    SQL工作流 - 基于LangGraph的有状态工作流

    工作流程：
    1. 意图分析 -> 2. Schema获取 -> 3. SQL生成 -> 4. 验证 -> 5. 执行 -> 6. 响应
    """

    def __init__(
        self,
        llm,
        tools: List,
        schema_manager: SchemaManager,
        prompt_manager: PromptManager,
        sql_validator: SQLValidator,
        db_connection: Optional[DatabaseConnection] = None
    ):
        """
        初始化SQL工作流

        Args:
            llm: LangChain兼容的LLM
            tools: 可用工具列表
            schema_manager: Schema管理器
            prompt_manager: 提示词管理器
            sql_validator: SQL验证器
            db_connection: 数据库连接
        """
        self.llm = llm
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}
        self.schema_manager = schema_manager
        self.prompt_manager = prompt_manager
        self.sql_validator = sql_validator
        self.db_connection = db_connection

        # 构建工作流图
        self.graph = self._build_graph()

        logger.info("SQLWorkflow初始化完成")

    def _build_graph(self) -> StateGraph:
        """构建工作流图"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("analyze_intent", self._analyze_intent_node)
        workflow.add_node("retrieve_schema", self._retrieve_schema_node)
        workflow.add_node("generate_sql", self._generate_sql_node)
        workflow.add_node("validate_sql", self._validate_sql_node)
        workflow.add_node("execute_sql", self._execute_sql_node)
        workflow.add_node("format_response", self._format_response_node)
        workflow.add_node("handle_error", self._handle_error_node)

        # 设置入口点
        workflow.set_entry_point("analyze_intent")

        # 添加边
        workflow.add_edge("analyze_intent", "retrieve_schema")
        workflow.add_edge("retrieve_schema", "generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")

        # 条件边
        workflow.add_conditional_edges(
            "validate_sql",
            self._should_execute,
            {
                "execute": "execute_sql",
                "error": "handle_error"
            }
        )

        workflow.add_edge("execute_sql", "format_response")
        workflow.add_edge("format_response", END)
        workflow.add_edge("handle_error", END)

        return workflow.compile()

    def _analyze_intent_node(self, state: AgentState) -> AgentState:
        """分析用户意图"""
        query = state.get("query", "").lower()

        if any(word in query for word in ["添加", "新增", "insert", "创建"]):
            operation = OperationType.INSERT
        elif any(word in query for word in ["修改", "更新", "update", "改变"]):
            operation = OperationType.UPDATE
        elif any(word in query for word in ["删除", "delete", "移除"]):
            operation = OperationType.DELETE
        elif any(word in query for word in ["查询", "查看", "select", "find", "获取"]):
            operation = OperationType.SELECT
        else:
            operation = OperationType.SELECT

        state["sql_type"] = operation.value
        state["steps"].append({
            "node": "analyze_intent",
            "operation": operation.value,
            "timestamp": datetime.now().isoformat()
        })

        return state

    def _retrieve_schema_node(self, state: AgentState) -> AgentState:
        """获取数据库Schema"""
        try:
            schema = self.schema_manager.get_full_schema()
            state["steps"].append({
                "node": "retrieve_schema",
                "tables_count": len(schema.get("tables", [])),
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            state["error"] = f"获取Schema失败: {str(e)}"

        return state

    async def _generate_sql_node(self, state: AgentState) -> AgentState:
        """生成SQL节点"""
        query = state.get("query", "")
        sql_type = state.get("sql_type", "select")

        try:
            # 获取表结构和业务规则
            schema_summary = self.schema_manager.get_table_summary()
            schema_text = "\n".join([
                f"- {t['table']}: {t['description']}"
                for t in schema_summary
            ])

            business_rules = self.prompt_manager.get_business_rules()
            business_rules_text = "\n".join([
                f"- {table}: {rule}"
                for table, rule in business_rules.items()
            ])

            # 构建提示词
            prompt = self.prompt_manager.get_sql_generation_prompt(
                database_structure=schema_text,
                query=query,
                business_rules=business_rules_text
            )

            # 调用LLM
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            response_text = response.content if hasattr(response, 'content') else str(response)

            # 提取SQL
            sql = self._extract_sql(response_text)
            state["sql"] = sql

            state["steps"].append({
                "node": "generate_sql",
                "sql": sql[:200] if sql else None,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            state["error"] = f"SQL生成失败: {str(e)}"

        return state

    def _extract_sql(self, text: str) -> str:
        """从响应中提取SQL"""
        import re
        # 移除代码块标记
        text = re.sub(r'```sql\n?', '', text)
        text = re.sub(r'```\n?', '', text)
        text = text.strip()

        # 如果包含JSON，尝试解析
        if text.startswith('{'):
            try:
                data = json.loads(text)
                return data.get('sql', text)
            except json.JSONDecodeError:
                pass

        return text

    def _validate_sql_node(self, state: AgentState) -> AgentState:
        """验证SQL"""
        sql = state.get("sql", "")

        if not sql:
            state["error"] = "SQL为空"
            return state

        validation_result = self.sql_validator.validate(sql)
        state["validation_result"] = validation_result

        # 评估风险
        sql_type = validation_result.get("sql_type", "")
        estimated_rows = self.schema_manager.estimate_affected_rows(sql)
        risk_level = self.sql_validator.evaluate_risk(sql, sql_type, estimated_rows)
        state["risk_level"] = risk_level

        state["steps"].append({
            "node": "validate_sql",
            "is_valid": validation_result.get("is_valid", False),
            "risk_level": risk_level,
            "timestamp": datetime.now().isoformat()
        })

        return state

    def _should_execute(self, state: AgentState) -> Literal["execute", "error"]:
        """决定是否执行SQL"""
        validation = state.get("validation_result", {})
        if validation.get("is_valid"):
            return "execute"
        return "error"

    def _execute_sql_node(self, state: AgentState) -> AgentState:
        """执行SQL"""
        if not self.db_connection:
            state["error"] = "数据库未配置"
            return state

        sql = state.get("sql", "")

        try:
            result = self.db_connection.execute_sql(sql, None)
            state["execution_result"] = result

            state["steps"].append({
                "node": "execute_sql",
                "success": result.get("success", False),
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            state["error"] = f"SQL执行失败: {str(e)}"

        return state

    def _format_response_node(self, state: AgentState) -> AgentState:
        """格式化响应"""
        response = {
            "success": True,
            "query": state.get("query"),
            "sql": state.get("sql"),
            "sql_type": state.get("sql_type"),
            "risk_level": state.get("risk_level"),
            "execution_result": state.get("execution_result"),
            "steps": state.get("steps", [])
        }

        state["response"] = json.dumps(response, ensure_ascii=False, indent=2)
        state["finished"] = True
        return state

    def _handle_error_node(self, state: AgentState) -> AgentState:
        """处理错误"""
        error = state.get("error", "未知错误")
        validation = state.get("validation_result", {})

        response = {
            "success": False,
            "query": state.get("query"),
            "error": error,
            "validation_errors": validation.get("errors", []),
            "steps": state.get("steps", [])
        }

        state["response"] = json.dumps(response, ensure_ascii=False, indent=2)
        state["finished"] = True
        return state

    async def ainvoke(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """异步执行工作流"""
        initial_state: AgentState = {
            "query": query,
            "user_context": user_context,
            "sql": None,
            "sql_type": None,
            "execution_result": None,
            "validation_result": None,
            "risk_level": None,
            "response": None,
            "error": None,
            "steps": [],
            "finished": False
        }

        try:
            result = await self.graph.ainvoke(initial_state)
            return {
                "success": True,
                "response": result.get("response"),
                "steps": result.get("steps", [])
            }
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

    def invoke(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """同步执行工作流"""
        import asyncio
        return asyncio.run(self.ainvoke(query, user_context))
