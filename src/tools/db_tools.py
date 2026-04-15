"""数据库工具定义"""
import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from ..database.connection import DatabaseConnection
from ..database.schema import SchemaManager
from ..database.prompts import PromptManager
from ..security.validator import SQLValidator

logger = logging.getLogger(__name__)


class GetSchemaInput(BaseModel):
    """获取数据库Schema输入"""
    table_name: Optional[str] = Field(None, description="可选，指定表名")


class GenerateSQLInput(BaseModel):
    """生成SQL输入"""
    query: str = Field(..., description="用户自然语言描述")
    user_context: Optional[Dict[str, Any]] = Field(None, description="用户上下文")


class ValidateSQLInput(BaseModel):
    """验证SQL输入"""
    sql: str = Field(..., description="要验证的SQL语句")


class ExecuteSQLInput(BaseModel):
    """执行SQL输入"""
    sql: str = Field(..., description="要执行的SQL语句")
    params: Optional[List[Any]] = Field(None, description="SQL参数")


class EstimateRowsInput(BaseModel):
    """预估行数输入"""
    sql: str = Field(..., description="SQL语句")


class GetStatusInput(BaseModel):
    """获取状态输入"""
    pass


def create_database_tools(
    db_connection: Optional[DatabaseConnection],
    schema_manager: SchemaManager,
    prompt_manager: PromptManager,
    sql_validator: SQLValidator,
    llm_client: Any = None
) -> List[StructuredTool]:
    """创建数据库工具集合"""

    tools = []

    # 1. 获取Schema工具
    def get_database_schema(table_name: Optional[str] = None) -> str:
        """获取数据库Schema信息"""
        try:
            if table_name:
                schema = schema_manager.get_table_schema(table_name)
                if schema is None:
                    return json.dumps({
                        "success": False,
                        "error": f"表 '{table_name}' 不存在"
                    }, ensure_ascii=False)
                return json.dumps({"tables": [schema]}, ensure_ascii=False, indent=2)
            else:
                schema = schema_manager.get_full_schema()
                return json.dumps(schema, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取Schema失败: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    tools.append(StructuredTool.from_function(
        func=get_database_schema,
        name="get_database_schema",
        description="获取数据库Schema信息（表结构、字段、说明）。无参数时返回所有表的信息。",
        args_schema=GetSchemaInput
    ))

    # 2. 生成SQL工具
    async def generate_sql(query: str, user_context: Optional[Dict[str, Any]] = None) -> str:
        """根据自然语言生成SQL语句"""
        try:
            # 获取表结构
            schema_summary = schema_manager.get_table_summary()
            schema_text = "\n".join([
                f"- {t['table']}: {t['description']}"
                for t in schema_summary
            ])

            # 获取业务规则
            business_rules = prompt_manager.get_business_rules()
            business_rules_text = "\n".join([
                f"- {table}: {rule}"
                for table, rule in business_rules.items()
            ])

            # 构建提示词
            prompt = prompt_manager.get_sql_generation_prompt(
                database_structure=schema_text,
                query=query,
                business_rules=business_rules_text
            )

            # 调用LLM生成SQL
            if llm_client:
                response = await llm_client.generate(prompt)
                return response

            return json.dumps({
                "sql": "",
                "error": "LLM客户端未配置"
            }, ensure_ascii=False)

        except Exception as e:
            logger.error(f"生成SQL失败: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    tools.append(StructuredTool.from_function(
        func=generate_sql,
        name="generate_sql",
        description="根据自然语言描述生成SQL语句",
        args_schema=GenerateSQLInput
    ))

    # 3. 验证SQL工具
    def validate_sql(sql: str) -> str:
        """验证SQL语句安全性"""
        try:
            result = sql_validator.validate(sql)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"验证SQL失败: {e}")
            return json.dumps({"is_valid": False, "errors": [str(e)]}, ensure_ascii=False)

    tools.append(StructuredTool.from_function(
        func=validate_sql,
        name="validate_sql",
        description="验证SQL语句是否安全和合规",
        args_schema=ValidateSQLInput
    ))

    # 4. 预估影响行数工具
    def estimate_affected_rows(sql: str) -> str:
        """预估SQL影响行数"""
        try:
            estimated_rows = schema_manager.estimate_affected_rows(sql)
            return json.dumps({"estimated_rows": estimated_rows}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"预估行数失败: {e}")
            return json.dumps({"estimated_rows": -1, "error": str(e)}, ensure_ascii=False)

    tools.append(StructuredTool.from_function(
        func=estimate_affected_rows,
        name="estimate_affected_rows",
        description="预估SQL语句将影响的行数",
        args_schema=EstimateRowsInput
    ))

    # 5. 执行SQL工具
    def execute_sql(sql: str, params: Optional[List[Any]] = None) -> str:
        """执行SQL语句"""
        try:
            if not db_connection:
                return json.dumps({
                    "success": False,
                    "error": "数据库未配置"
                }, ensure_ascii=False)

            # 先验证SQL
            validation = sql_validator.validate(sql)
            if not validation.get("is_valid"):
                return json.dumps({
                    "success": False,
                    "error": "SQL验证失败",
                    "validation": validation
                }, ensure_ascii=False)

            # 执行SQL
            result = db_connection.execute_sql(sql, params)
            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"执行SQL失败: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    tools.append(StructuredTool.from_function(
        func=execute_sql,
        name="execute_sql",
        description="执行SQL语句并返回结果。SELECT返回查询结果，UPDATE/INSERT/DELETE返回影响行数。",
        args_schema=ExecuteSQLInput
    ))

    # 6. 获取服务器状态工具
    def get_server_status() -> str:
        """获取服务器状态"""
        try:
            from datetime import datetime
            status = {
                "server": {
                    "name": "db-ai-server",
                    "version": "2.0.0",
                    "started_at": datetime.now().isoformat()
                },
                "database": {
                    "tables_count": len(schema_manager.get_all_table_names())
                }
            }
            return json.dumps(status, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    tools.append(StructuredTool.from_function(
        func=get_server_status,
        name="get_server_status",
        description="获取服务器状态和配置信息",
        args_schema=GetStatusInput
    ))

    return tools
