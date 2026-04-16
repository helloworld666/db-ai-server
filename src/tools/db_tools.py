"""数据库工具定义 - LangChain v1.0 规范

使用@tool装饰器定义工具，工具描述从配置文件动态加载。
代码中不包含任何硬编码的业务逻辑或提示词。
"""
import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from ..database.connection import DatabaseConnection
from ..database.schema import SchemaManager
from ..security.validator import SQLValidator

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic输入模型定义
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


# ============================================================================
# 工具工厂函数 - 创建带依赖注入的工具实例
# ============================================================================

def create_database_tools(
    db_connection: Optional[DatabaseConnection],
    schema_manager: SchemaManager,
    sql_validator: SQLValidator,
    tool_descriptions: Optional[Dict[str, str]] = None
) -> List:
    """
    创建数据库工具集合
    
    Args:
        db_connection: 数据库连接对象
        schema_manager: Schema管理器
        sql_validator: SQL验证器
        tool_descriptions: 工具描述配置（从配置文件加载）
    
    Returns:
        工具对象列表
    """
    descriptions = tool_descriptions or {}
    tools = []

    # -------------------------------------------------------------------------
    # 1. 获取Schema工具
    # -------------------------------------------------------------------------
    @tool(args_schema=GetSchemaInput)
    def get_database_schema(table_name: Optional[str] = None) -> str:
        """
        获取数据库Schema信息
        
        返回数据库表结构信息。如果不提供table_name，返回所有表的信息。
        """
        try:
            if table_name:
                schema = schema_manager.get_table_schema(table_name)
                if schema is None:
                    return json.dumps({
                        "success": False,
                        "error": f"Table '{table_name}' not found"
                    }, ensure_ascii=False)
                return json.dumps({"tables": [schema]}, ensure_ascii=False, indent=2)
            else:
                schema = schema_manager.get_full_schema()
                return json.dumps(schema, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取Schema失败: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    tools.append(get_database_schema)

    # -------------------------------------------------------------------------
    # 2. 执行SQL工具
    # -------------------------------------------------------------------------
    @tool(args_schema=ExecuteSQLInput)
    def execute_sql(sql: str) -> str:
        """
        执行SQL语句
        
        执行SQL语句并返回结果。支持SELECT、INSERT、UPDATE、DELETE操作。
        """
        try:
            if not db_connection:
                return json.dumps({
                    "success": False,
                    "error": "数据库未配置"
                }, ensure_ascii=False)

            # 验证SQL
            validation = sql_validator.validate(sql)
            if not validation.get("is_valid"):
                return json.dumps({
                    "success": False,
                    "error": "SQL验证失败",
                    "validation": validation
                }, ensure_ascii=False)

            # 根据SQL类型执行
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
    @tool(args_schema=ValidateSQLInput)
    def validate_sql(sql: str) -> str:
        """
        验证SQL语句安全性
        
        检查SQL语句是否存在注入风险、语法错误等问题。
        """
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
    @tool()
    def get_server_status() -> str:
        """
        获取服务器状态信息
        
        返回服务器版本、数据库连接状态、表数量等信息。
        """
        try:
            from datetime import datetime
            status = {
                "server": {
                    "name": "db-ai-server",
                    "version": "5.0.0",
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
