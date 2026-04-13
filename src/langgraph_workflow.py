"""
LangGraph 工作流实现
使用 LangGraph 构建有状态、多步骤的数据库操作工作流
"""

import json
import logging
from typing import Dict, Any, List, Optional, Literal, TypedDict, Annotated, Sequence
from datetime import datetime
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """操作类型枚举"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    UNKNOWN = "unknown"


class AgentState(TypedDict):
    """
    Agent 状态定义
    使用 TypedDict 定义 LangGraph 的状态
    """
    # 用户查询
    query: str
    # 用户上下文
    user_context: Optional[Dict[str, Any]]
    # 生成的SQL
    sql: Optional[str]
    # SQL类型
    sql_type: Optional[str]
    # 执行结果
    execution_result: Optional[Dict[str, Any]]
    # 验证结果
    validation_result: Optional[Dict[str, Any]]
    # 风险等级
    risk_level: Optional[str]
    # 最终响应
    response: Optional[str]
    # 错误信息
    error: Optional[str]
    # 执行步骤历史
    steps: List[Dict[str, Any]]
    # 操作是否完成
    finished: bool


class DatabaseWorkflow:
    """
    基于 LangGraph 的数据库操作工作流

    支持的工作流：
    1. 查询工作流: 分析查询 -> 生成SQL -> 验证 -> 执行 -> 返回结果
    2. 插入工作流: 分析插入 -> 生成SQL -> 验证 -> 执行 -> 验证结果 -> 返回
    3. 更新工作流: 分析更新 -> 生成SQL -> 验证 -> 执行 -> 验证结果 -> 返回
    4. 删除工作流: 分析删除 -> 生成SQL -> 验证 -> 执行 -> 确认 -> 返回
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Sequence[BaseTool],
        config_loader,
        validate_sql_func,
        evaluate_risk_func
    ):
        """
        初始化 LangGraph 工作流

        Args:
            llm: LangChain 兼容的聊天模型
            tools: LangChain 工具列表
            config_loader: 配置加载器
            validate_sql_func: SQL验证函数
            evaluate_risk_func: 风险评估函数
        """
        self.llm = llm
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}
        self.config_loader = config_loader
        self.validate_sql = validate_sql_func
        self.evaluate_risk = evaluate_risk_func

        # 构建工作流图
        self.graph = self._build_graph()

        # 记忆系统
        self.memory: List[Dict] = []

        logger.info("LangGraph DatabaseWorkflow 初始化完成")

    def _build_graph(self) -> StateGraph:
        """构建工作流图"""
        # 创建状态图
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("analyze_intent", self._analyze_intent_node)
        workflow.add_node("generate_sql", self._generate_sql_node)
        workflow.add_node("validate_sql", self._validate_sql_node)
        workflow.add_node("execute_sql", self._execute_sql_node)
        workflow.add_node("verify_result", self._verify_result_node)
        workflow.add_node("format_response", self._format_response_node)
        workflow.add_node("handle_error", self._handle_error_node)

        # 设置入口点
        workflow.set_entry_point("analyze_intent")

        # 添加边
        workflow.add_edge("analyze_intent", "generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")

        # 验证后根据结果分支
        workflow.add_conditional_edges(
            "validate_sql",
            self._should_execute,
            {
                "execute": "execute_sql",
                "error": "handle_error"
            }
        )

        # 执行后验证结果
        workflow.add_edge("execute_sql", "verify_result")
        workflow.add_edge("verify_result", "format_response")
        workflow.add_edge("format_response", END)
        workflow.add_edge("handle_error", END)

        return workflow.compile()

    def _analyze_intent_node(self, state: AgentState) -> AgentState:
        """分析用户意图节点"""
        query = state.get("query", "").lower()

        # 分析操作类型
        if any(word in query for word in ["添加", "新增", "insert", "创建", "增加"]):
            operation = OperationType.INSERT
        elif any(word in query for word in ["修改", "更新", "update", "改变", "编辑"]):
            operation = OperationType.UPDATE
        elif any(word in query for word in ["删除", "delete", "移除", "去掉"]):
            operation = OperationType.DELETE
        elif any(word in query for word in ["查询", "查看", "select", "find", "搜索", "获取"]):
            operation = OperationType.SELECT
        else:
            operation = OperationType.SELECT  # 默认按查询处理

        state["sql_type"] = operation.value
        state["steps"].append({
            "node": "analyze_intent",
            "operation": operation.value,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"意图分析完成: {operation.value}")
        return state

    async def _generate_sql_node(self, state: AgentState) -> AgentState:
        """生成SQL节点"""
        query = state.get("query", "")
        user_context = state.get("user_context", {})
        sql_type = state.get("sql_type", "select")

        # 初始化SQL变量
        sql = ""
        
        # 使用 LM Studio 生成 SQL
        try:
            # 从配置文件中读取提示词和数据库结构
            import json
            import os
            
            # 尝试从配置文件中读取提示词
            config_path = os.path.join(os.path.dirname(__file__), "..", "config", "prompts.json")
            prompt_template = ""
            
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        if "sql_generation" in config:
                            prompt_template = config["sql_generation"]
                except Exception as e:
                    logger.error(f"读取提示词配置失败: {e}")
            
            # 不使用默认提示词，提示词必须从配置文件中读取
            
            # 从database_schema.json文件中读取数据库结构
            database_structure = ""
            schema_path = os.path.join(os.path.dirname(__file__), "..", "config", "database_schema.json")
            if os.path.exists(schema_path):
                try:
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        schema = json.load(f)
                        tables = schema.get("tables", [])
                        for table in tables:
                            table_name = table.get("name", "")
                            table_desc = table.get("description", "")
                            database_structure += f"- {table_name}：{table_desc}\n"
                except Exception as e:
                    logger.error(f"读取数据库结构失败: {e}")
            
            # 构建提示词
            prompt = prompt_template.format(database_structure=database_structure, query=query)
            logger.info(f"生成SQL提示词: {prompt[:100]}...")

            # 调用 AI 生成 SQL
            from langchain_core.messages import HumanMessage
            try:
                # 直接使用 llm 生成，而不是 agenerate
                try:
                    # 尝试使用 invoke 方法
                    ai_response = await self.llm.ainvoke([HumanMessage(content=prompt)])
                    logger.info(f"AI生成响应: {ai_response}")
                    
                    # 提取生成的SQL
                    if hasattr(ai_response, 'content'):
                        response_text = ai_response.content
                    elif isinstance(ai_response, str):
                        response_text = ai_response
                    else:
                        response_text = str(ai_response)
                    
                    logger.info(f"AI生成文本: {response_text}")
                    
                    # 提取SQL语句
                    # 移除可能的SQL标记
                    import re
                    sql_match = re.search(r'```(?:sql)?\n(.*?)\n```', response_text, re.DOTALL)
                    if sql_match:
                        sql = sql_match.group(1).strip()
                    else:
                        sql = response_text.strip()
                    
                    # 不进行表名映射，直接使用LM Studio生成的SQL
                except Exception as e:
                    logger.error(f"调用AI生成SQL失败: {e}")
                    sql = ""
            except Exception as e:
                logger.error(f"调用AI生成SQL失败: {e}")
                sql = ""
            
            # 如果没有生成SQL，不使用默认SQL，让LM Studio生成的SQL直接执行
            if not sql:
                sql = ""
        except Exception as e:
            state["error"] = f"SQL生成失败: {str(e)}"
            logger.error(f"SQL生成失败: {e}")
            # 不使用默认SQL，让LM Studio生成的SQL直接执行
            sql = ""
        
        # 不确保SQL不为空，让LM Studio生成的SQL直接执行
        
        # 更新状态
        state["sql"] = sql
        state["steps"].append({
            "node": "generate_sql",
            "sql": sql,
            "timestamp": datetime.now().isoformat()
        })
        logger.info(f"SQL生成完成: {sql}")

        return state

    def _validate_sql_node(self, state: AgentState) -> AgentState:
        """验证SQL节点"""
        sql = state.get("sql", "")

        if not sql:
            state["error"] = "SQL为空"
            return state

        # 使用验证函数
        validation_result = self.validate_sql(sql)
        state["validation_result"] = validation_result

        # 评估风险
        risk_level = self.evaluate_risk({
            "sql": sql,
            "sql_type": state.get("sql_type", "")
        })
        state["risk_level"] = risk_level

        state["steps"].append({
            "node": "validate_sql",
            "is_valid": validation_result.get("is_valid", False),
            "risk_level": risk_level,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"SQL验证完成: is_valid={validation_result.get('is_valid')}, risk={risk_level}")
        return state

    def _should_execute(self, state: AgentState) -> Literal["execute", "error"]:
        """决定是否执行SQL"""
        validation = state.get("validation_result", {})
        if validation.get("is_valid"):
            return "execute"
        return "error"

    def _execute_sql_node(self, state: AgentState) -> AgentState:
        """执行SQL节点"""
        from src.database_connector import DatabaseConnector

        sql = state.get("sql", "")
        db_config = self.config_loader.get("server.database.connection_string")

        if not db_config:
            state["error"] = "数据库未配置"
            return state

        try:
            db_connector = DatabaseConnector(db_config)
            result = db_connector.execute_sql(sql, None)
            state["execution_result"] = result
            state["steps"].append({
                "node": "execute_sql",
                "success": result.get("success", False),
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            state["error"] = f"SQL执行失败: {str(e)}"
            state["steps"].append({
                "node": "execute_sql",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

        return state

    def _verify_result_node(self, state: AgentState) -> AgentState:
        """验证结果节点"""
        result = state.get("execution_result", {})
        sql_type = state.get("sql_type", "")

        verification = {
            "verified": True,
            "message": "操作成功"
        }

        if not result.get("success", False):
            verification["verified"] = False
            verification["message"] = result.get("error", "执行失败")
        elif sql_type in ["insert", "update", "delete"]:
            if result.get("affected_rows", 0) == 0:
                verification["warning"] = "操作未影响任何行"

        state["steps"].append({
            "node": "verify_result",
            "verification": verification,
            "timestamp": datetime.now().isoformat()
        })

        return state

    def _format_response_node(self, state: AgentState) -> AgentState:
        """格式化响应节点"""
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
        return state

    def _handle_error_node(self, state: AgentState) -> AgentState:
        """处理错误节点"""
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
        return state

    def _build_sql_prompt(
        self,
        query: str,
        user_context: Dict[str, Any],
        sql_type: str
    ) -> str:
        """构建SQL生成提示词"""
        prompts_config = self.config_loader.get_prompts_config()

        prompt_parts = []
        prompt_parts.append(prompts_config.get('system_prompt', ''))
        prompt_parts.append(f"\n请生成一个 {sql_type} 类型的SQL语句。")
        prompt_parts.append(f"\n用户查询: {query}")

        if user_context:
            prompt_parts.append(f"\n用户上下文: {json.dumps(user_context, ensure_ascii=False)}")

        return "\n".join(prompt_parts)

    async def ainvoke(self, query: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        异步执行工作流

        Args:
            query: 用户查询
            user_context: 用户上下文

        Returns:
            工作流执行结果
        """
        logger.info(f"LangGraph Workflow 执行: {query}")

        # 初始化状态
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
            # 执行工作流
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

    def invoke(self, query: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        同步执行工作流

        Args:
            query: 用户查询
            user_context: 用户上下文

        Returns:
            工作流执行结果
        """
        logger.info(f"LangGraph Workflow 执行(同步): {query}")

        # 初始化状态
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
            # 执行工作流
            result = self.graph.invoke(initial_state)
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

    def add_memory(self, content: str, metadata: Dict = None):
        """添加记忆"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "metadata": metadata or {}
        }
        self.memory.append(entry)

    def get_memory_summary(self, max_entries: int = 10) -> List[Dict]:
        """获取记忆摘要"""
        return self.memory[-max_entries:] if len(self.memory) > max_entries else self.memory
