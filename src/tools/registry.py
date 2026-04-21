"""工具注册表 - LangChain v1.0 标准

使用LangChain标准@tool装饰器定义工具
工具描述从配置文件动态加载
"""
import json
import logging
from typing import Dict, Any, Optional, List, Callable
from langchain_core.tools import tool, BaseTool
from pydantic import BaseModel, Field

from ..schema.manager import SchemaManager
from ..database.connection import DatabaseConnection
from ..security.validator import SQLValidator
from ..prompts.manager import PromptManager


def _build_tool_description(description: str, constraints: list) -> str:
    """构建工具描述，包含描述和约束"""
    desc = description
    if constraints:
        desc += "\n\n【约束】"
        for constraint in constraints:
            desc += f"\n- {constraint}"
    return desc


logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic输入模型 - LangChain v1.0 标准
# ============================================================================

class GetSchemaInput(BaseModel):
    """获取数据库Schema的输入参数"""
    table_name: Optional[str] = Field(
        default=None,
        description="可选，指定表名。不提供则返回所有表"
    )


class ExecuteSQLInput(BaseModel):
    """执行SQL的输入参数"""
    sql: str = Field(
        ...,
        description="要执行的SQL语句"
    )


class ValidateSQLInput(BaseModel):
    """验证SQL的输入参数"""
    sql: str = Field(
        ...,
        description="要验证的SQL语句"
    )


class GetServerStatusInput(BaseModel):
    """获取服务器状态的输入参数"""
    pass


# ============================================================================
# 工具工厂函数
# ============================================================================

def create_database_tools(
    db_connection: Optional[DatabaseConnection],
    schema_manager: SchemaManager,
    sql_validator: SQLValidator,
    prompt_manager: Optional[PromptManager] = None,
    include_validate: bool = True
) -> List[BaseTool]:
    """
    创建数据库工具集合

    Args:
        db_connection: 数据库连接对象
        schema_manager: Schema管理器
        sql_validator: SQL验证器
        prompt_manager: 提示词管理器（用于获取工具描述）
        include_validate: 是否包含validate_sql工具

    Returns:
        LangChain工具对象列表
    """
    tools = []

    # 获取工具配置
    schema_tool_config = prompt_manager.get_tool_config("get_database_schema") if prompt_manager else None
    execute_tool_config = prompt_manager.get_tool_config("execute_sql") if prompt_manager else None
    validate_tool_config = prompt_manager.get_tool_config("validate_sql") if prompt_manager else None
    status_tool_config = prompt_manager.get_tool_config("get_server_status") if prompt_manager else None

    # -------------------------------------------------------------------------
    # 1. 获取Schema工具
    # -------------------------------------------------------------------------
    schema_desc = (schema_tool_config.get("description", "") + "\n\n返回格式：\n- database_name: 数据库名\n- tables: 表列表，每项包含name(表名)、description(描述)、columns(字段列表)\n- columns每项包含：name(字段名)、type(类型)、description(说明)") if schema_tool_config else "获取数据库Schema信息（表结构、字段、说明）"
    schema_constraints = schema_tool_config.get("constraints", []) if schema_tool_config else []
    schema_full_desc = _build_tool_description(schema_desc, schema_constraints)

    @tool(args_schema=GetSchemaInput, description=schema_full_desc)
    def get_database_schema(table_name: Optional[str] = None) -> str:
        try:
            if table_name:
                schema = schema_manager.get_table_schema(table_name)
                if schema is None:
                    return f"错误：表 '{table_name}' 不存在。请使用不带参数的调用获取所有表名。"
                result = {
                    "表名": schema.get("name"),
                    "描述": schema.get("description", ""),
                    "字段": []
                }
                for col in schema.get("columns", []):
                    field_info = {
                        "字段名": col.get("name"),
                        "类型": col.get("type"),
                        "说明": col.get("description", "")
                    }
                    # 返回SQL约束信息（放在前面，更醒目）
                    if col.get("sql_constraint"):
                        field_info["⚠️重要约束"] = col.get("sql_constraint")
                    # 标记敏感字段
                    if col.get("sensitive"):
                        field_info["敏感"] = "是"
                    result["字段"].append(field_info)
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                schema = schema_manager.get_full_schema()
                result = {
                    "数据库": schema.get("database_name", ""),
                    "所有表": []
                }
                for table in schema.get("tables", []):
                    result["所有表"].append({
                        "表名": table.get("name"),
                        "描述": table.get("description", "")
                    })
                return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取Schema失败: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    tools.append(get_database_schema)

    # -------------------------------------------------------------------------
    # 2. 执行SQL工具（仅在提供db_connection时创建）
    # -------------------------------------------------------------------------
    if db_connection is not None:
        execute_desc = execute_tool_config.get("description", "执行SQL语句并返回结果") if execute_tool_config else "执行SQL语句并返回结果"
        execute_constraints = execute_tool_config.get("constraints", []) if execute_tool_config else []
        execute_full_desc = _build_tool_description(execute_desc, execute_constraints)

        @tool(args_schema=ExecuteSQLInput, description=execute_full_desc)
        def execute_sql(sql: str) -> str:
            try:
                validation = sql_validator.validate(sql)
                if not validation.get("is_valid"):
                    return json.dumps({
                        "success": False,
                        "error": "SQL验证失败",
                        "validation": validation
                    }, ensure_ascii=False)

                sql_type = validation.get("sql_type", "").upper()

                if sql_type == "SELECT":
                    result = db_connection.execute_query(sql)
                else:
                    result = db_connection.execute_update(sql)

                return json.dumps(result, ensure_ascii=False, indent=2)

            except Exception as e:
                logger.error(f"执行SQL失败: {e}")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        tools.append(execute_sql)

    # -------------------------------------------------------------------------
    # 3. 验证SQL工具
    # -------------------------------------------------------------------------
    if include_validate:
        validate_desc = validate_tool_config.get("description", "验证SQL语句安全性") if validate_tool_config else "验证SQL语句安全性"
        validate_constraints = validate_tool_config.get("constraints", []) if validate_tool_config else []
        validate_full_desc = _build_tool_description(validate_desc, validate_constraints)

        @tool(args_schema=ValidateSQLInput, description=validate_full_desc)
        def validate_sql(sql: str) -> str:
            try:
                result = sql_validator.validate(sql)
                return json.dumps(result, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"验证SQL失败: {e}")
                return json.dumps({"is_valid": False, "errors": [str(e)]}, ensure_ascii=False)

        tools.append(validate_sql)

    # -------------------------------------------------------------------------
    # 4. 获取服务器状态工具
    # -------------------------------------------------------------------------
    status_desc = status_tool_config.get("description", "获取服务器状态信息") if status_tool_config else "获取服务器状态信息"
    status_constraints = status_tool_config.get("constraints", []) if status_tool_config else []
    status_full_desc = _build_tool_description(status_desc, status_constraints)

    @tool(args_schema=GetServerStatusInput, description=status_full_desc)
    def get_server_status() -> str:
        try:
            from datetime import datetime
            status = {
                "server": {
                    "name": "db-ai-server",
                    "version": "7.0.0",
                    "architecture": "langchain_v1",
                    "started_at": datetime.now().isoformat()
                },
                "database": {
                    "connected": db_connection is not None,
                    "tables_count": len(schema_manager.get_all_table_names())
                }
            }
            return json.dumps(status, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    tools.append(get_server_status)

    return tools


# ============================================================================
# 工具注册表
# ============================================================================

class ToolRegistry:
    """
    工具注册表 - 管理所有可用工具

    统一管理工具的创建、配置和访问
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tool_factories: Dict[str, Callable] = {}

    def register(self, name: str, tool: BaseTool):
        """注册工具"""
        self._tools[name] = tool
        logger.info(f"已注册工具: {name}")

    def register_factory(self, name: str, factory: Callable):
        """注册工具工厂"""
        self._tool_factories[name] = factory
        logger.info(f"已注册工具工厂: {name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)

    def get_all_tools(self) -> List[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())

    def list_tool_names(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())


def create_tool_registry(
    db_connection: Optional[DatabaseConnection],
    schema_manager: SchemaManager,
    sql_validator: SQLValidator,
    prompt_manager: Optional[PromptManager] = None,
    include_execute: bool = True,
    include_validate: bool = True
) -> ToolRegistry:
    """
    创建工具注册表

    Args:
        db_connection: 数据库连接
        schema_manager: Schema管理器
        sql_validator: SQL验证器
        prompt_manager: 提示词管理器
        include_execute: 是否包含执行SQL工具
        include_validate: 是否包含验证SQL工具

    Returns:
        配置好的工具注册表
    """
    registry = ToolRegistry()

    # 创建工具
    tools = create_database_tools(
        db_connection=db_connection if include_execute else None,
        schema_manager=schema_manager,
        sql_validator=sql_validator,
        prompt_manager=prompt_manager,
        include_validate=include_validate
    )

    # 注册工具
    for t in tools:
        registry.register(t.name, t)

    return registry
