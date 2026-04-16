"""数据库工具定义 - 遵循LangChain官方标准

参考: https://langchain-doc.cn/v1/python/langchain/tools.html
"""
import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from langchain.tools import tool

from ..database.connection import DatabaseConnection
from ..database.schema import SchemaManager
from ..database.prompts import PromptManager
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


class GenerateSQLInput(BaseModel):
    """生成SQL的输入参数"""
    query: str = Field(
        ...,
        description="用户的自然语言查询描述"
    )


class ValidateSQLInput(BaseModel):
    """验证SQL的输入参数"""
    sql: str = Field(
        ...,
        description="要验证的SQL语句"
    )


class ExecuteQueryInput(BaseModel):
    """执行查询的输入参数"""
    sql: str = Field(
        ...,
        description="SELECT查询语句"
    )
    params: Optional[List[Any]] = Field(
        default=None,
        description="SQL参数列表"
    )


class ExecuteUpdateInput(BaseModel):
    """执行更新的输入参数"""
    sql: str = Field(
        ...,
        description="INSERT/UPDATE/DELETE语句"
    )
    params: Optional[List[Any]] = Field(
        default=None,
        description="SQL参数列表"
    )


class EstimateRowsInput(BaseModel):
    """预估行数的输入参数"""
    sql: str = Field(
        ...,
        description="SQL语句"
    )


# ============================================================================
# 工具函数 - 使用@tool装饰器（LangChain标准做法）
# ============================================================================

@tool(args_schema=GetSchemaInput)
def get_database_schema(table_name: Optional[str] = None) -> str:
    """获取数据库Schema信息。

    返回数据库表结构信息，包括表名、字段、类型、注释等。
    如果不提供table_name，返回所有表的信息。

    Args:
        table_name: 可选，指定表名

    Returns:
        JSON格式的Schema信息
    """
    # 实际实现会在create_tools中注入依赖
    raise NotImplementedError("工具需要在create_tools中创建")


@tool(args_schema=GenerateSQLInput)
def generate_sql(query: str) -> str:
    """根据自然语言描述生成SQL语句。

    将用户的自然语言查询转换为可执行的SQL语句。
    支持SELECT、INSERT、UPDATE、DELETE等操作。

    Args:
        query: 用户的自然语言查询描述

    Returns:
        生成的SQL语句或错误信息
    """
    raise NotImplementedError("工具需要在create_tools中创建")


@tool(args_schema=ValidateSQLInput)
def validate_sql(sql: str) -> str:
    """验证SQL语句的安全性。

    检查SQL语句是否存在注入风险、语法错误等问题。

    Args:
        sql: 要验证的SQL语句

    Returns:
        JSON格式的验证结果
    """
    raise NotImplementedError("工具需要在create_tools中创建")


@tool(args_schema=ExecuteQueryInput)
def execute_query(sql: str, params: Optional[List[Any]] = None) -> str:
    """执行SELECT查询语句。

    执行查询类SQL语句并返回结果。仅支持SELECT操作。

    Args:
        sql: SELECT查询语句
        params: SQL参数列表

    Returns:
        JSON格式的查询结果
    """
    raise NotImplementedError("工具需要在create_tools中创建")


@tool(args_schema=ExecuteUpdateInput)
def execute_update(sql: str, params: Optional[List[Any]] = None) -> str:
    """执行INSERT/UPDATE/DELETE操作。

    执行数据修改类SQL语句并返回影响行数。
    支持INSERT、UPDATE、DELETE操作。

    Args:
        sql: INSERT/UPDATE/DELETE语句
        params: SQL参数列表

    Returns:
        JSON格式的执行结果
    """
    raise NotImplementedError("工具需要在create_tools中创建")


@tool(args_schema=EstimateRowsInput)
def estimate_affected_rows(sql: str) -> str:
    """预估SQL语句影响的行数。

    分析SQL语句，预估可能影响的行数范围。

    Args:
        sql: SQL语句

    Returns:
        JSON格式的预估结果
    """
    raise NotImplementedError("工具需要在create_tools中创建")


@tool()
def get_server_status() -> str:
    """获取服务器状态信息。

    返回服务器版本、数据库连接状态、表数量等信息。

    Returns:
        JSON格式的状态信息
    """
    raise NotImplementedError("工具需要在create_tools中创建")


# ============================================================================
# 工具工厂函数 - 创建带依赖注入的工具实例
# ============================================================================

def create_database_tools(
    db_connection: Optional[DatabaseConnection],
    schema_manager: SchemaManager,
    prompt_manager: PromptManager,
    sql_validator: SQLValidator,
    llm_client: Any = None
) -> List[Any]:
    """创建数据库工具集合

    使用LangChain标准的@tool装饰器方式创建工具，
    通过闭包注入依赖（db_connection, schema_manager等）。

    Args:
        db_connection: 数据库连接对象
        schema_manager: Schema管理器
        prompt_manager: 提示词管理器
        sql_validator: SQL验证器
        llm_client: LLM客户端

    Returns:
        工具对象列表
    """
    tools = []

    # -------------------------------------------------------------------------
    # 1. 获取Schema工具
    # -------------------------------------------------------------------------
    @tool(args_schema=GetSchemaInput)
    def _get_database_schema(table_name: Optional[str] = None) -> str:
        """获取数据库Schema信息。

        返回数据库表结构信息，包括表名、字段、类型、注释等。
        如果不提供table_name，返回所有表的信息。

        Args:
            table_name: 可选，指定表名

        Returns:
            JSON格式的Schema信息
        """
        try:
            if not db_connection:
                # 如果数据库未连接，回退到配置文件
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

            # 动态从数据库获取表结构
            if table_name:
                schema_info = _get_table_schema_from_db(db_connection, table_name)
                if schema_info is None:
                    return json.dumps({
                        "success": False,
                        "error": f"Table '{table_name}' not found in database"
                    }, ensure_ascii=False)
                return json.dumps({"tables": [schema_info]}, ensure_ascii=False, indent=2)
            else:
                all_tables = _get_all_tables_from_db(db_connection)
                return json.dumps({
                    "database_name": "dynamic_database",
                    "database_type": "mysql",
                    "tables": all_tables
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"获取Schema失败: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    tools.append(_get_database_schema)

    # -------------------------------------------------------------------------
    # 2. 生成SQL工具
    # -------------------------------------------------------------------------
    @tool(args_schema=GenerateSQLInput)
    async def _generate_sql(query: str) -> str:
        """根据自然语言描述生成SQL语句。

        将用户的自然语言查询转换为可执行的SQL语句。
        直接返回纯SQL语句，不返回JSON格式。

        Args:
            query: 用户的自然语言查询描述

        Returns:
            生成的SQL语句
        """
        try:
            # 获取表结构摘要
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
                "success": False,
                "error": "LLM客户端未配置"
            }, ensure_ascii=False)

        except Exception as e:
            logger.error(f"生成SQL失败: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    tools.append(_generate_sql)

    # -------------------------------------------------------------------------
    # 3. 验证SQL工具
    # -------------------------------------------------------------------------
    @tool(args_schema=ValidateSQLInput)
    def _validate_sql(sql: str) -> str:
        """验证SQL语句的安全性。

        检查SQL语句是否存在注入风险、语法错误等问题。

        Args:
            sql: 要验证的SQL语句

        Returns:
            JSON格式的验证结果
        """
        try:
            result = sql_validator.validate(sql)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"验证SQL失败: {e}")
            return json.dumps({"is_valid": False, "errors": [str(e)]}, ensure_ascii=False)

    tools.append(_validate_sql)

    # -------------------------------------------------------------------------
    # 4. 预估影响行数工具
    # -------------------------------------------------------------------------
    @tool(args_schema=EstimateRowsInput)
    def _estimate_affected_rows(sql: str) -> str:
        """预估SQL语句影响的行数。

        分析SQL语句，预估可能影响的行数范围。

        Args:
            sql: SQL语句

        Returns:
            JSON格式的预估结果
        """
        try:
            estimated_rows = schema_manager.estimate_affected_rows(sql)
            return json.dumps({"estimated_rows": estimated_rows}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"预估行数失败: {e}")
            return json.dumps({"estimated_rows": -1, "error": str(e)}, ensure_ascii=False)

    tools.append(_estimate_affected_rows)

    # -------------------------------------------------------------------------
    # 5. 执行SELECT查询工具
    # -------------------------------------------------------------------------
    @tool(args_schema=ExecuteQueryInput)
    def _execute_query(sql: str, params: Optional[List[Any]] = None) -> str:
        """执行SELECT查询语句。

        执行查询类SQL语句并返回结果。仅支持SELECT操作。

        Args:
            sql: SELECT查询语句
            params: SQL参数列表

        Returns:
            JSON格式的查询结果
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

            # 执行查询
            result = db_connection.execute_query(sql, params)

            # 应用 display_mapping 转换
            if result.get("success") and result.get("rows"):
                result = _apply_display_mapping(result, sql, schema_manager)

            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"执行SELECT查询失败: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    tools.append(_execute_query)

    # -------------------------------------------------------------------------
    # 6. 执行更新操作工具
    # -------------------------------------------------------------------------
    @tool(args_schema=ExecuteUpdateInput)
    def _execute_update(sql: str, params: Optional[List[Any]] = None) -> str:
        """执行INSERT/UPDATE/DELETE操作。

        执行数据修改类SQL语句并返回影响行数。
        支持INSERT、UPDATE、DELETE操作。

        Args:
            sql: INSERT/UPDATE/DELETE语句
            params: SQL参数列表

        Returns:
            JSON格式的执行结果
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

            # 执行更新
            result = db_connection.execute_update(sql, params)
            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"执行更新操作失败: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    tools.append(_execute_update)

    # -------------------------------------------------------------------------
    # 7. 获取服务器状态工具
    # -------------------------------------------------------------------------
    @tool()
    def _get_server_status() -> str:
        """获取服务器状态信息。

        返回服务器版本、数据库连接状态、表数量等信息。

        Returns:
            JSON格式的状态信息
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
                    "tables_count": len(schema_manager.get_all_table_names())
                }
            }
            return json.dumps(status, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    tools.append(_get_server_status)

    return tools


# ============================================================================
# 辅助函数
# ============================================================================

def _get_all_tables_from_db(db_conn: DatabaseConnection) -> List[Dict[str, Any]]:
    """从数据库动态获取所有表结构"""
    try:
        tables_result = db_conn.execute_query("""
            SELECT TABLE_NAME, TABLE_COMMENT
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
        """)

        tables = []
        if tables_result.get("success") and tables_result.get("rows"):
            for row in tables_result["rows"]:
                table_name = row.get("TABLE_NAME") or row.get("table_name")
                table_comment = row.get("TABLE_COMMENT") or row.get("table_comment") or ""

                columns = _get_columns_from_db(db_conn, table_name)

                tables.append({
                    "name": table_name,
                    "description": table_comment if table_comment else f"Table {table_name}",
                    "columns": columns
                })

        return tables
    except Exception as e:
        logger.error(f"从数据库获取表列表失败: {e}")
        return []


def _get_table_schema_from_db(db_conn: DatabaseConnection, table_name: str) -> Optional[Dict[str, Any]]:
    """从数据库获取指定表的详细结构"""
    try:
        table_result = db_conn.execute_query("""
            SELECT TABLE_NAME, TABLE_COMMENT
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        """, [table_name])

        if not table_result.get("success") or not table_result.get("rows"):
            return None

        row = table_result["rows"][0]
        actual_table_name = row.get("TABLE_NAME") or row.get("table_name")
        table_comment = row.get("TABLE_COMMENT") or row.get("table_comment") or ""

        columns = _get_columns_from_db(db_conn, actual_table_name)

        return {
            "name": actual_table_name,
            "description": table_comment if table_comment else f"Table {actual_table_name}",
            "columns": columns
        }
    except Exception as e:
        logger.error(f"从数据库获取表结构失败: {e}")
        return None


def _get_columns_from_db(db_conn: DatabaseConnection, table_name: str) -> List[Dict[str, Any]]:
    """从数据库获取指定表的列信息"""
    try:
        columns_result = db_conn.execute_query("""
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                COLUMN_COMMENT,
                IS_NULLABLE,
                COLUMN_KEY,
                EXTRA
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, [table_name])

        columns = []
        if columns_result.get("success") and columns_result.get("rows"):
            for col in columns_result["rows"]:
                col_name = col.get("COLUMN_NAME") or col.get("column_name")
                data_type = col.get("DATA_TYPE") or col.get("data_type")
                col_comment = col.get("COLUMN_COMMENT") or col.get("column_comment") or ""
                is_nullable = col.get("IS_NULLABLE") or col.get("is_nullable")
                column_key = col.get("COLUMN_KEY") or col.get("column_key")
                extra = col.get("EXTRA") or col.get("extra") or ""

                column_info = {
                    "name": col_name,
                    "type": data_type,
                    "description": col_comment if col_comment else f"Column {col_name}",
                    "required": is_nullable == "NO",
                    "primary_key": column_key == "PRI",
                    "auto_increment": "auto_increment" in extra.lower()
                }
                columns.append(column_info)

        return columns
    except Exception as e:
        logger.error(f"从数据库获取列信息失败: {e}")
        return []


def _apply_display_mapping(result: Dict[str, Any], sql: str, schema_manager: SchemaManager) -> Dict[str, Any]:
    """对查询结果应用display_mapping转换"""
    import re

    data = result.get("rows", [])
    if not data or not isinstance(data, list):
        return result

    # 从SQL中提取表名
    table_names = set()
    patterns = [r'(?:FROM|JOIN)\s+[`"]?([a-zA-Z_][a-zA-Z0-9_]*)[`"]?']

    for pattern in patterns:
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            table_name = match.group(1).lower()
            table_names.add(table_name)

    if not table_names:
        return result

    # 构建字段映射
    field_to_info = {}
    for table_name in table_names:
        table_mappings = schema_manager.get_table_display_mappings(table_name)
        for col_name, mapping_info in table_mappings.items():
            if mapping_info.get("display_mapping"):
                field_to_info[col_name.lower()] = {
                    "output_name": mapping_info.get("output_name", col_name),
                    "mapping": mapping_info["display_mapping"]
                }

    if not field_to_info:
        return result

    # 转换数据
    converted_data = []
    for row in data:
        if isinstance(row, dict):
            new_row = {}
            for key, value in row.items():
                key_lower = key.lower().strip('`')
                if key_lower in field_to_info:
                    info = field_to_info[key_lower]
                    new_row[info["output_name"]] = info["mapping"].get(str(value), value)
                else:
                    new_row[key] = value
            converted_data.append(new_row)
        else:
            converted_data.append(row)

    result["rows"] = converted_data
    return result
