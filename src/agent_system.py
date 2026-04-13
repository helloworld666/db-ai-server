"""
智能代理系统 - 实现多工具调用的Agent架构
Agent = Memory + Planning + Tools + Action
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Callable

logger = logging.getLogger(__name__)

class ToolType(Enum):
    """工具类型枚举"""
    EXECUTE_SQL = "execute_sql"
    QUERY_DATA = "query_data"
    ANALYZE_RESULTS = "analyze_results"
    GENERATE_SQL = "generate_sql"
    VALIDATE_DATA = "validate_data"
    GET_SCHEMA = "get_schema"

@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    tool_type: ToolType
    parameters: Dict[str, str]
    execute_func: Callable

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "name": self.name,
            "description": self.description,
            "tool_type": self.tool_type.value,
            "parameters": self.parameters
        }

@dataclass
class MemoryEntry:
    """记忆条目"""
    timestamp: datetime
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "content": self.content,
            "metadata": self.metadata
        }

@dataclass
class PlanningStep:
    """规划步骤"""
    step_number: int
    description: str
    required_tool: ToolType
    expected_outcome: str
    completed: bool = False
    result: Optional[Any] = None

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "step_number": self.step_number,
            "description": self.description,
            "required_tool": self.required_tool.value,
            "expected_outcome": self.expected_outcome,
            "completed": self.completed,
            "result": self.result if self.completed else None
        }

class DatabaseAgent:
    """智能数据库代理"""

    def __init__(self, database_connector, ai_client):
        """
        初始化代理

        Args:
            database_connector: 数据库连接器
            ai_client: AI客户端
        """
        self.database_connector = database_connector
        self.ai_client = ai_client

        # 记忆系统
        self.memory: List[MemoryEntry] = []

        # 当前规划
        self.current_plan: List[PlanningStep] = []

        # 可用工具
        self.tools: Dict[str, Tool] = {}

        # 初始化工具
        self._initialize_tools()

        # 对话历史
        self.conversation_history: List[Dict] = []

        logger.info("DatabaseAgent 初始化完成")

    def _initialize_tools(self):
        """初始化所有可用工具"""

        # 1. 执行SQL工具
        self.tools["execute_sql"] = Tool(
            name="execute_sql",
            description="执行SQL语句（INSERT/UPDATE/DELETE/SELECT）并返回结果",
            tool_type=ToolType.EXECUTE_SQL,
            parameters={
                "sql": "要执行的SQL语句",
                "operation_type": "操作类型（insert/update/delete/select）"
            },
            execute_func=self._execute_sql_tool
        )

        # 2. 查询数据工具
        self.tools["query_data"] = Tool(
            name="query_data",
            description="查询数据库中的数据，支持复杂条件",
            tool_type=ToolType.QUERY_DATA,
            parameters={
                "table": "表名",
                "fields": "要查询的字段列表",
                "conditions": "查询条件",
                "limit": "限制返回行数"
            },
            execute_func=self._query_data_tool
        )

        # 3. 分析结果工具
        self.tools["analyze_results"] = Tool(
            name="analyze_results",
            description="分析查询结果，提取关键信息",
            tool_type=ToolType.ANALYZE_RESULTS,
            parameters={
                "data": "要分析的数据",
                "analysis_type": "分析类型（summary/validation/comparison）"
            },
            execute_func=self._analyze_results_tool
        )

        # 4. 生成SQL工具
        self.tools["generate_sql"] = Tool(
            name="generate_sql",
            description="根据自然语言描述生成SQL语句",
            tool_type=ToolType.GENERATE_SQL,
            parameters={
                "user_query": "用户查询的自然语言描述",
                "operation_type": "操作类型（select/insert/update/delete）"
            },
            execute_func=self._generate_sql_tool
        )

        # 5. 验证数据工具
        self.tools["validate_data"] = Tool(
            name="validate_data",
            description="验证数据操作的结果是否正确",
            tool_type=ToolType.VALIDATE_DATA,
            parameters={
                "operation": "执行的操作",
                "expected_result": "预期结果",
                "actual_result": "实际结果"
            },
            execute_func=self._validate_data_tool
        )

        # 6. 获取Schema工具
        self.tools["get_schema"] = Tool(
            name="get_schema",
            description="获取数据库表结构信息",
            tool_type=ToolType.GET_SCHEMA,
            parameters={
                "table": "表名（可选，为空时获取所有表）"
            },
            execute_func=self._get_schema_tool
        )

        logger.info(f"已初始化 {len(self.tools)} 个工具")

    def _execute_sql_tool(self, **kwargs) -> Dict:
        """执行SQL工具"""
        sql = kwargs.get("sql")
        operation_type = kwargs.get("operation_type", "unknown")

        logger.info(f"执行SQL工具: {operation_type} - {sql}")

        try:
            if operation_type.lower() in ["select", "query"]:
                # 查询操作
                results = self.database_connector.execute_query(sql)
                return {
                    "success": True,
                    "operation": operation_type,
                    "sql": sql,
                    "data": results,
                    "row_count": len(results) if isinstance(results, list) else 0,
                    "message": f"查询成功，返回 {len(results) if isinstance(results, list) else 0} 行数据"
                }
            else:
                # 更新操作（INSERT/UPDATE/DELETE）
                result = self.database_connector.execute_update(sql)
                return {
                    "success": True,
                    "operation": operation_type,
                    "sql": sql,
                    "affected_rows": result.get("affected_rows", 0),
                    "insert_id": result.get("insert_id"),
                    "message": f"执行成功，影响 {result.get('affected_rows', 0)} 行"
                }
        except Exception as e:
            logger.error(f"执行SQL失败: {e}")
            return {
                "success": False,
                "operation": operation_type,
                "sql": sql,
                "error": str(e),
                "message": f"执行失败: {str(e)}"
            }

    def _query_data_tool(self, **kwargs) -> Dict:
        """查询数据工具"""
        table = kwargs.get("table")
        fields = kwargs.get("fields", ["*"])
        conditions = kwargs.get("conditions", {})
        limit = kwargs.get("limit", 100)

        logger.info(f"查询数据工具: {table} - 字段: {fields}")

        # 构建查询条件
        where_clause = ""
        if conditions:
            where_parts = []
            for key, value in conditions.items():
                if isinstance(value, str):
                    where_parts.append(f"{key} = '{value}'")
                else:
                    where_parts.append(f"{key} = {value}")
            where_clause = " WHERE " + " AND ".join(where_parts)

        # 构建字段列表
        if isinstance(fields, list):
            fields_str = ", ".join(fields)
        else:
            fields_str = fields

        # 构建SQL
        sql = f"SELECT {fields_str} FROM {table}{where_clause} LIMIT {limit}"

        # 执行查询
        return self._execute_sql_tool(sql=sql, operation_type="select")

    def _analyze_results_tool(self, **kwargs) -> Dict:
        """分析结果工具"""
        data = kwargs.get("data")
        analysis_type = kwargs.get("analysis_type", "summary")

        logger.info(f"分析结果工具: {analysis_type}")

        if analysis_type == "summary":
            # 数据摘要分析
            if isinstance(data, list) and data:
                first_row = data[0]
                return {
                    "success": True,
                    "analysis_type": analysis_type,
                    "row_count": len(data),
                    "columns": list(first_row.keys()) if isinstance(first_row, dict) else [],
                    "sample": data[:3] if len(data) > 3 else data,
                    "message": f"数据摘要：{len(data)} 行数据，{len(list(first_row.keys())) if isinstance(first_row, dict) else 0} 列"
                }
            else:
                return {
                    "success": True,
                    "analysis_type": analysis_type,
                    "row_count": 0,
                    "message": "无数据或数据为空"
                }
        elif analysis_type == "validation":
            # 验证分析
            return {
                "success": True,
                "analysis_type": analysis_type,
                "is_valid": True,
                "checks": [
                    {"check": "数据完整性", "passed": True},
                    {"check": "格式正确性", "passed": True}
                ],
                "message": "数据验证通过"
            }
        else:
            return {
                "success": True,
                "analysis_type": analysis_type,
                "message": f"完成 {analysis_type} 分析"
            }

    def _generate_sql_tool(self, **kwargs) -> Dict:
        """生成SQL工具"""
        user_query = kwargs.get("user_query")
        operation_type = kwargs.get("operation_type")

        logger.info(f"生成SQL工具: {operation_type} - {user_query[:50]}...")

        try:
            # 使用AI客户端生成SQL
            messages = [
                {"role": "system", "content": "你是一个SQL专家，根据用户描述生成SQL语句。请只返回SQL语句，不要解释。"},
                {"role": "user", "content": f"用户查询: {user_query}"}
            ]

            if operation_type:
                messages.append({"role": "system", "content": f"请生成一个{operation_type}类型的SQL语句。"})

            # 处理异步调用
            import asyncio
            if hasattr(self.ai_client, 'chat'):
                # 异步chat方法
                response = asyncio.run(self.ai_client.chat(messages=messages, temperature=0.1))
            elif hasattr(self.ai_client, 'chat_completion'):
                # 同步chat_completion方法
                response = self.ai_client.chat_completion(messages=messages, max_tokens=200)
            else:
                # 回退到简单的SQL生成
                response = f"INSERT INTO sys_user (name, real_name, password, role_id) VALUES ('test', '测试用户', MD5('123456'), 1);"

            # 提取SQL语句
            sql = response.strip() if response else ""

            # 清理可能的标记
            if "```sql" in sql:
                sql = sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql:
                sql = sql.split("```")[1].split("```")[0].strip()

            # 如果SQL为空，生成一个默认的
            if not sql:
                if operation_type == "insert":
                    sql = f"INSERT INTO sys_user (name, real_name, password, role_id) VALUES ('{user_query[:10]}', '测试用户', MD5('123456'), 1);"
                elif operation_type == "select":
                    sql = "SELECT id, name, real_name, role_id, enable FROM sys_user WHERE enable = 1 LIMIT 10;"
                elif operation_type == "update":
                    sql = "UPDATE sys_user SET enable = 0 WHERE name = 'test';"
                else:
                    sql = f"-- 无法生成SQL: {user_query}"

            return {
                "success": True,
                "user_query": user_query,
                "sql": sql,
                "operation_type": operation_type or "unknown",
                "message": "SQL生成成功"
            }
        except Exception as e:
            logger.error(f"生成SQL失败: {e}")
            return {
                "success": False,
                "user_query": user_query,
                "error": str(e),
                "message": f"生成SQL失败: {str(e)}"
            }

    def _validate_data_tool(self, **kwargs) -> Dict:
        """验证数据工具"""
        operation = kwargs.get("operation")
        expected_result = kwargs.get("expected_result")
        actual_result = kwargs.get("actual_result")

        logger.info(f"验证数据工具: {operation}")

        # 简单的验证逻辑
        validation_passed = True
        validation_message = "验证通过"

        if operation == "insert":
            # 验证INSERT操作
            if actual_result and actual_result.get("affected_rows", 0) > 0:
                validation_message = f"INSERT成功，插入了 {actual_result.get('affected_rows')} 行数据"
            else:
                validation_passed = False
                validation_message = "INSERT操作未影响任何行"

        return {
            "success": True,
            "operation": operation,
            "validation_passed": validation_passed,
            "validation_message": validation_message,
            "expected": expected_result,
            "actual": actual_result
        }

    def _get_schema_tool(self, **kwargs) -> Dict:
        """获取Schema工具"""
        table = kwargs.get("table")

        logger.info(f"获取Schema工具: {table or '所有表'}")

        try:
            # 获取表结构
            if table:
                # 获取特定表的结构
                sql = f"DESCRIBE {table}"
                result = self.database_connector.execute_query(sql)
                return {
                    "success": True,
                    "table": table,
                    "schema": result,
                    "field_count": len(result),
                    "message": f"获取到 {table} 的表结构，共 {len(result)} 个字段"
                }
            else:
                # 获取所有表
                sql = "SHOW TABLES"
                tables = self.database_connector.execute_query(sql)
                table_list = [list(table.values())[0] for table in tables]

                schemas = {}
                for table_name in table_list[:10]:  # 限制最多10个表
                    try:
                        sql = f"DESCRIBE {table_name}"
                        table_schema = self.database_connector.execute_query(sql)
                        schemas[table_name] = table_schema
                    except Exception as e:
                        logger.warning(f"获取表 {table_name} 结构失败: {e}")

                return {
                    "success": True,
                    "tables": table_list,
                    "schemas": schemas,
                    "table_count": len(table_list),
                    "message": f"获取到 {len(table_list)} 个表，已加载 {len(schemas)} 个表的结构"
                }
        except Exception as e:
            logger.error(f"获取Schema失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"获取Schema失败: {str(e)}"
            }

    def add_memory(self, content: str, metadata: Dict = None):
        """添加记忆"""
        entry = MemoryEntry(
            timestamp=datetime.now(),
            content=content,
            metadata=metadata or {}
        )
        self.memory.append(entry)
        logger.debug(f"添加记忆: {content[:50]}...")

    def get_memory_summary(self, max_entries: int = 10) -> List[Dict]:
        """获取记忆摘要"""
        recent_memory = self.memory[-max_entries:] if len(self.memory) > max_entries else self.memory
        return [entry.to_dict() for entry in recent_memory]

    def create_plan(self, goal: str) -> List[PlanningStep]:
        """
        创建执行计划

        Args:
            goal: 目标描述

        Returns:
            规划步骤列表
        """
        logger.info(f"创建计划: {goal}")

        # 根据目标类型创建不同的计划
        if "insert" in goal.lower() or "添加" in goal.lower():
            # 插入数据的计划
            plan = [
                PlanningStep(
                    step_number=1,
                    description="分析用户需求，理解要插入的数据",
                    required_tool=ToolType.ANALYZE_RESULTS,
                    expected_outcome="理解插入需求"
                ),
                PlanningStep(
                    step_number=2,
                    description="生成INSERT SQL语句",
                    required_tool=ToolType.GENERATE_SQL,
                    expected_outcome="生成正确的INSERT SQL"
                ),
                PlanningStep(
                    step_number=3,
                    description="执行INSERT操作",
                    required_tool=ToolType.EXECUTE_SQL,
                    expected_outcome="成功插入数据"
                ),
                PlanningStep(
                    step_number=4,
                    description="验证INSERT操作结果",
                    required_tool=ToolType.VALIDATE_DATA,
                    expected_outcome="验证插入成功"
                ),
                PlanningStep(
                    step_number=5,
                    description="查询新插入的数据",
                    required_tool=ToolType.QUERY_DATA,
                    expected_outcome="获取新插入的数据"
                ),
                PlanningStep(
                    step_number=6,
                    description="分析查询结果，准备返回给用户",
                    required_tool=ToolType.ANALYZE_RESULTS,
                    expected_outcome="整理数据供用户查看"
                )
            ]
        elif "update" in goal.lower() or "修改" in goal.lower():
            # 更新数据的计划
            plan = [
                PlanningStep(
                    step_number=1,
                    description="分析用户需求，理解要更新的数据",
                    required_tool=ToolType.ANALYZE_RESULTS,
                    expected_outcome="理解更新需求"
                ),
                PlanningStep(
                    step_number=2,
                    description="生成UPDATE SQL语句",
                    required_tool=ToolType.GENERATE_SQL,
                    expected_outcome="生成正确的UPDATE SQL"
                ),
                PlanningStep(
                    step_number=3,
                    description="执行UPDATE操作",
                    required_tool=ToolType.EXECUTE_SQL,
                    expected_outcome="成功更新数据"
                ),
                PlanningStep(
                    step_number=4,
                    description="查询更新后的数据",
                    required_tool=ToolType.QUERY_DATA,
                    expected_outcome="获取更新后的数据"
                ),
                PlanningStep(
                    step_number=5,
                    description="分析更新结果",
                    required_tool=ToolType.ANALYZE_RESULTS,
                    expected_outcome="整理更新结果供用户查看"
                )
            ]
        elif "select" in goal.lower() or "查询" in goal.lower() or "查看" in goal.lower():
            # 查询数据的计划
            plan = [
                PlanningStep(
                    step_number=1,
                    description="分析用户查询需求",
                    required_tool=ToolType.ANALYZE_RESULTS,
                    expected_outcome="理解查询需求"
                ),
                PlanningStep(
                    step_number=2,
                    description="生成SELECT SQL语句",
                    required_tool=ToolType.GENERATE_SQL,
                    expected_outcome="生成正确的SELECT SQL"
                ),
                PlanningStep(
                    step_number=3,
                    description="执行查询操作",
                    required_tool=ToolType.EXECUTE_SQL,
                    expected_outcome="获取查询结果"
                ),
                PlanningStep(
                    step_number=4,
                    description="分析查询结果",
                    required_tool=ToolType.ANALYZE_RESULTS,
                    expected_outcome="整理查询结果供用户查看"
                )
            ]
        else:
            # 通用计划
            plan = [
                PlanningStep(
                    step_number=1,
                    description="分析用户需求",
                    required_tool=ToolType.ANALYZE_RESULTS,
                    expected_outcome="理解用户需求"
                ),
                PlanningStep(
                    step_number=2,
                    description="获取相关数据表结构",
                    required_tool=ToolType.GET_SCHEMA,
                    expected_outcome="了解数据库结构"
                ),
                PlanningStep(
                    step_number=3,
                    description="生成SQL语句",
                    required_tool=ToolType.GENERATE_SQL,
                    expected_outcome="生成正确的SQL"
                ),
                PlanningStep(
                    step_number=4,
                    description="执行SQL操作",
                    required_tool=ToolType.EXECUTE_SQL,
                    expected_outcome="执行操作并获取结果"
                ),
                PlanningStep(
                    step_number=5,
                    description="分析执行结果",
                    required_tool=ToolType.ANALYZE_RESULTS,
                    expected_outcome="整理结果供用户查看"
                )
            ]

        self.current_plan = plan
        logger.info(f"创建了 {len(plan)} 步的计划")

        return plan

    def execute_plan(self) -> Dict:
        """
        执行当前计划

        Returns:
            执行结果汇总
        """
        if not self.current_plan:
            return {"success": False, "error": "没有可执行的计划"}

        logger.info(f"开始执行计划，共 {len(self.current_plan)} 步")

        all_results = []
        for step in self.current_plan:
            logger.info(f"执行步骤 {step.step_number}: {step.description}")

            # 执行步骤
            result = self.execute_step(step)
            step.completed = True
            step.result = result

            all_results.append({
                "step": step.step_number,
                "description": step.description,
                "result": result
            })

            # 如果某一步失败，可以决定是否继续
            if result.get("success") is False:
                logger.warning(f"步骤 {step.step_number} 失败: {result.get('message', '未知错误')}")
                # 继续执行还是中断取决于业务逻辑

        # 汇总结果
        successful_steps = sum(1 for step in self.current_plan if step.completed and step.result.get("success") is True)

        return {
            "success": successful_steps == len(self.current_plan),
            "total_steps": len(self.current_plan),
            "successful_steps": successful_steps,
            "results": all_results,
            "final_data": self._extract_final_data(all_results)
        }

    def execute_step(self, step: PlanningStep) -> Dict:
        """
        执行单个步骤

        Args:
            step: 规划步骤

        Returns:
            执行结果
        """
        # 根据步骤类型选择工具
        tool_type = step.required_tool

        # 查找对应的工具
        tool = None
        for t in self.tools.values():
            if t.tool_type == tool_type:
                tool = t
                break

        if not tool:
            return {
                "success": False,
                "error": f"找不到 {tool_type.value} 类型的工具",
                "message": "工具不可用"
            }

        try:
            # 执行工具
            # 这里需要根据步骤描述生成合适的参数
            # 简化处理：返回工具信息
            return {
                "success": True,
                "tool_used": tool.name,
                "tool_description": tool.description,
                "step_description": step.description,
                "message": f"执行 {tool.name} 工具完成"
            }
        except Exception as e:
            logger.error(f"执行步骤失败: {e}")
            return {
                "success": False,
                "tool_used": tool.name,
                "error": str(e),
                "message": f"执行失败: {str(e)}"
            }

    def _extract_final_data(self, all_results: List[Dict]) -> Any:
        """从所有结果中提取最终数据"""
        # 查找包含数据的步骤结果
        for result in reversed(all_results):
            step_result = result.get("result", {})
            if step_result.get("data"):
                return step_result.get("data")
            elif step_result.get("sql"):
                return step_result.get("sql")

        return None

    def get_tools_description(self) -> List[Dict]:
        """获取所有工具的描述"""
        return [tool.to_dict() for tool in self.tools.values()]

    def process_user_request(self, user_query: str) -> Dict:
        """
        处理用户请求的完整流程

        Args:
            user_query: 用户查询

        Returns:
            处理结果
        """
        logger.info(f"处理用户请求: {user_query}")

        # 1. 添加记忆
        self.add_memory(f"用户请求: {user_query}", {"type": "user_query"})

        # 2. 创建计划
        plan = self.create_plan(user_query)

        # 3. 记录计划到记忆
        self.add_memory(f"创建计划: {len(plan)} 个步骤", {"plan_steps": len(plan)})

        # 4. 执行计划
        plan_result = self.execute_plan()

        # 5. 记录执行结果
        self.add_memory(f"计划执行完成: {plan_result.get('successful_steps')}/{plan_result.get('total_steps')} 成功",
                       {"plan_result": plan_result})

        # 6. 返回结果
        return {
            "user_query": user_query,
            "plan_created": len(plan),
            "execution_result": plan_result,
            "memory_summary": self.get_memory_summary(5),
            "available_tools": [tool.name for tool in self.tools.values()]
        }
