"""
LangChain Agent 工具定义
使用 LangChain 的 Tool 装饰器定义数据库操作工具
"""

import json
import logging
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel, Field



logger = logging.getLogger(__name__)


class GetSchemaInput(BaseModel):
    """获取数据库Schema输入参数"""
    table_name: Optional[str] = Field(None, description="可选，指定表名以获取特定表的Schema")


class GenerateSQLInput(BaseModel):
    """生成SQL输入参数"""
    query: str = Field(..., description="用户自然语言描述")
    user_context: Optional[Dict[str, Any]] = Field(None, description="用户上下文信息")


class ValidateSQLInput(BaseModel):
    """验证SQL输入参数"""
    sql: str = Field(..., description="要验证的SQL语句")


class EstimateRowsInput(BaseModel):
    """预估影响行数输入参数"""
    sql: str = Field(..., description="SQL语句")


class ExecuteSQLInput(BaseModel):
    """执行SQL输入参数"""
    sql: str = Field(..., description="要执行的SQL语句")
    params: Optional[List[Any]] = Field(None, description="SQL参数")


class IntelligentlyExecuteInput(BaseModel):
    """智能执行输入参数"""
    query: str = Field(..., description="用户自然语言描述")
    user_context: Optional[Dict[str, Any]] = Field(None, description="用户上下文信息")


class DatabaseTools:
    """数据库工具集合"""

    def __init__(
        self,
        schema_manager,
        db_connector,
        ai_client,
        config_loader,
        validate_sql_func,
        evaluate_risk_func,
        generate_suggestions_func,
        parse_ai_response_func,
        build_sql_prompt_func
    ):
        """
        初始化数据库工具

        Args:
            schema_manager: Schema管理器实例
            db_connector: 数据库连接器
            ai_client: AI客户端
            config_loader: 配置加载器
            validate_sql_func: SQL验证函数
            evaluate_risk_func: 风险评估函数
            generate_suggestions_func: 生成建议函数
            parse_ai_response_func: 解析AI响应函数
            build_sql_prompt_func: 构建SQL提示词函数
        """
        self.schema_manager = schema_manager
        self.db_connector = db_connector
        self.ai_client = ai_client
        self.config_loader = config_loader
        self.validate_sql = validate_sql_func
        self.evaluate_risk = evaluate_risk_func
        self.generate_suggestions = generate_suggestions_func
        self.parse_ai_response = parse_ai_response_func
        self.build_sql_prompt = build_sql_prompt_func

    def get_database_schema(self, table_name: Optional[str] = None) -> str:
        """
        获取数据库Schema信息（表结构、字段、说明）

        Args:
            table_name: 可选，指定表名以获取特定表的Schema

        Returns:
            简化的表结构信息（表名和字段列表）
        """
        import asyncio
        try:
            if table_name:
                schema = self.schema_manager.config_loader.get_table_schema(table_name)
                if schema is None:
                    return json.dumps({
                        "success": False,
                        "error": f"表 '{table_name}' 不存在"
                    }, ensure_ascii=False, indent=2)
            else:
                schema = asyncio.run(self.schema_manager.get_full_schema())

            # 返回简洁的表列表，让 LLM 从 description 推断
            tables_info = []
            for table in schema.get("tables", []):
                tables_info.append({
                    "table": table.get("name"),
                    "desc": table.get("description", "")
                })
            return json.dumps({"tables": tables_info}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取Schema失败: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)

    async def generate_sql(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        根据自然语言描述生成SELECT/UPDATE/INSERT/DELETE SQL语句

        Args:
            query: 用户自然语言描述
            user_context: 用户上下文信息

        Returns:
            JSON格式的SQL生成结果
        """
        try:
            # 构建提示词
            prompt = self.build_sql_prompt(query, user_context or {})

            # 调用AI生成SQL
            ai_response = await self.ai_client.generate(prompt)
            logger.info(f"AI原始响应: {ai_response[:500]}")

            # 解析响应
            response_data = self.parse_ai_response(ai_response)

            # 检查SQL中是否包含占位符
            import re
            sql = response_data.get("sql", "")
            if sql:
                placeholder_pattern = r'(\?|%\d*[sdfe]|%\([^)]+\)|\$\d|\bparam\d*\b)'
                if re.search(placeholder_pattern, sql, re.IGNORECASE):
                    error_msg = "数据库操做描述不够具体。请提供更明确的描述，例如：\n"
                    error_msg += "- '更新货架编号为***的货架,将其编号更改为***'\n"
                    error_msg += "- '更新用户名为***的用户为可用状态'"
                    response_data["sql"] = ""
                    response_data["error"] = error_msg
                    response_data["explanation"] = error_msg
                    response_data["risk_level"] = "high"
                    return json.dumps(response_data, ensure_ascii=False, indent=2)

            # 验证SQL
            validation_result = self.validate_sql(response_data.get("sql", ""))
            response_data["validation"] = validation_result

            # 评估风险
            response_data["risk_level"] = self.evaluate_risk(response_data)

            # 生成优化建议
            sql_type = validation_result.get("sql_type", "")
            suggestions = self.generate_suggestions(response_data.get("sql", ""), sql_type)
            if suggestions and "suggestions" not in response_data:
                response_data["suggestions"] = suggestions

            return json.dumps(response_data, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"生成SQL失败: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)

    def validate_sql_tool(self, sql: str) -> str:
        """
        验证生成的SQL语句是否安全和合规

        Args:
            sql: 要验证的SQL语句

        Returns:
            JSON格式的验证结果
        """
        try:
            result = self.validate_sql(sql)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"验证SQL失败: {e}")
            return json.dumps({
                "is_valid": False,
                "errors": [str(e)]
            }, ensure_ascii=False, indent=2)

    def estimate_affected_rows(self, sql: str) -> str:
        """
        预估SQL语句将影响的行数

        Args:
            sql: SQL语句

        Returns:
            JSON格式的预估结果
        """
        try:
            estimated_rows = self.schema_manager.estimate_affected_rows(sql)
            return json.dumps({
                "estimated_rows": estimated_rows
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"预估影响行数失败: {e}")
            return json.dumps({
                "estimated_rows": -1,
                "error": str(e)
            }, ensure_ascii=False, indent=2)

    def execute_sql(self, sql: str, params: Optional[List[Any]] = None) -> str:
        """
        执行SQL语句并返回结果（SELECT返回查询结果，UPDATE/INSERT/DELETE返回影响行数）

        Args:
            sql: 要执行的SQL语句
            params: SQL参数

        Returns:
            JSON格式的执行结果
        """
        try:
            # 检查数据库连接
            if not self.db_connector:
                return json.dumps({
                    "success": False,
                    "error": "数据库未配置或连接失败"
                }, ensure_ascii=False, indent=2)

            # 验证SQL
            validation_result = self.validate_sql(sql)
            if not validation_result.get("is_valid"):
                return json.dumps({
                    "success": False,
                    "error": "SQL验证失败",
                    "validation": validation_result
                }, ensure_ascii=False, indent=2)

            # 执行SQL
            result = self.db_connector.execute_sql(sql, params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"执行SQL失败: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)

    def get_server_status(self) -> str:
        """
        获取服务器状态和配置信息

        Returns:
            JSON格式的服务器状态
        """
        try:
            from datetime import datetime
            status = {
                "server": {
                    "name": self.config_loader.get('server.name'),
                    "version": self.config_loader.get('server.version'),
                    "description": self.config_loader.get('server.description'),
                    "started_at": datetime.now().isoformat()
                },
                "inference_engine": self.config_loader.get_inference_config(),
                "database": {
                    "database_name": self.config_loader.get('database_schema.database_name'),
                    "database_type": self.config_loader.get('database_schema.database_type'),
                    "tables_count": len(self.config_loader.get('database_schema.tables', []))
                }
            }

            if 'inference_engine' in status:
                status['inference_engine']['connected'] = (
                    self.ai_client.is_connected if self.ai_client else False
                )

            return json.dumps(status, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取服务器状态失败: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)

    def get_tools(self) -> List:
        """获取所有工具实例"""
        from langchain_core.tools import StructuredTool

        tools = []

        # 关键修复：不使用装饰器，直接定义函数并绑定 self
        # 这样避免 @tool 装饰器转换后导致的 StructuredTool 不可调用问题

        # 直接使用实例方法的引用（不用装饰器包装）
        execute_sql_func = self.execute_sql
        validate_sql_func = self.validate_sql_tool
        get_schema_func = self.get_database_schema
        estimate_rows_func = self.estimate_affected_rows
        get_status_func = self.get_server_status
        generate_sql_func = self.generate_sql

        tools.append(StructuredTool.from_function(
            func=execute_sql_func,
            name="execute_sql",
            description="执行SQL语句并返回结果（SELECT返回查询结果，UPDATE/INSERT/DELETE返回影响行数）",
            args_schema=ExecuteSQLInput
        ))

        tools.append(StructuredTool.from_function(
            func=validate_sql_func,
            name="validate_sql",
            description="验证生成的SQL语句是否安全和合规",
            args_schema=ValidateSQLInput
        ))

        tools.append(StructuredTool.from_function(
            func=get_schema_func,
            name="get_database_schema",
            description="获取数据库Schema信息（表结构、字段、说明）",
            args_schema=GetSchemaInput
        ))

        tools.append(StructuredTool.from_function(
            func=estimate_rows_func,
            name="estimate_affected_rows",
            description="预估SQL语句将影响的行数",
            args_schema=EstimateRowsInput
        ))

        tools.append(StructuredTool.from_function(
            func=get_status_func,
            name="get_server_status",
            description="获取服务器状态和配置信息"
        ))

        return tools
