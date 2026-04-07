#!/usr/bin/env python3
"""
db-ai-server MCP Server
通用的MCP服务器，用于AI驱动的数据库SQL生成
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional, List
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        ListToolsResult,
        TextContent,
    )
except ImportError:
    print("错误: 未安装mcp包，请运行: pip install mcp")
    sys.exit(1)

from src.config_loader import get_config_loader
from src.ollama_client import OllamaClient
from src.schema_manager import SchemaManager
from src.database_connector import DatabaseConnector

# 配置日志
def setup_logging():
    """配置日志系统"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'mcp_server.log', encoding='utf-8'),
            logging.StreamHandler(sys.stderr)  # 输出到stderr，避免干扰MCP协议通信
        ]
    )

setup_logging()
logger = logging.getLogger(__name__)

# 全局变量
server: Optional[Server] = None
ollama_client: Optional[OllamaClient] = None
schema_manager: Optional[SchemaManager] = None
db_connector: Optional[DatabaseConnector] = None


def initialize_server():
    """初始化服务器组件"""
    global server, ollama_client, schema_manager, db_connector
    
    # 加载配置
    logger.info("Initializing db-ai-server MCP Server...")
    
    config_loader = get_config_loader()
    ollama_config = config_loader.get_ollama_config()
    
    # 初始化Ollama客户端
    ollama_client = OllamaClient(
        base_url=ollama_config.get('base_url', 'http://localhost:11434/api'),
        model=ollama_config.get('model', 'qwen3:8b'),
        timeout=ollama_config.get('timeout', 120),
        max_retries=ollama_config.get('max_retries', 3)
    )
    
    schema_manager = SchemaManager(config_loader)
    
    # 初始化数据库连接器（如果配置了连接字符串）
    db_config = config_loader.get('server.database', {})
    connection_string = db_config.get('connection_string')
    if connection_string:
        try:
            db_connector = DatabaseConnector(connection_string)
            logger.info("数据库连接器已初始化")
        except Exception as e:
            logger.warning(f"数据库连接器初始化失败: {e}")
            db_connector = None
    else:
        logger.info("未配置数据库连接字符串，SQL执行功能将不可用")
        db_connector = None
    
    # 创建MCP Server
    server = Server("db-ai-server")
    
    # 注册工具
    _register_tools()
    
    logger.info("db-ai-server MCP Server initialized successfully")
    return server


def _register_tools():
    """注册MCP工具"""
    
    @server.list_tools()
    async def list_tools() -> ListToolsResult:
        """列出所有可用的工具"""
        tools = [
            Tool(
                name="get_database_schema",
                description="获取数据库Schema信息（表结构、字段、说明）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "可选，指定表名以获取特定表的Schema"
                        }
                    }
                }
            ),
            Tool(
                name="generate_sql",
                description="根据自然语言描述生成SELECT/UPDATE/INSERT/DELETE SQL语句",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "用户自然语言描述，例如：查询所有激活的用户；修改用户表，将所有未激活用户的status字段改为active"
                        },
                        "user_context": {
                            "type": "object",
                            "description": "用户上下文信息（可选）",
                            "properties": {
                                "username": {"type": "string"},
                                "role": {"type": "string"},
                                "permissions": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            }
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="validate_sql",
                description="验证生成的SQL语句是否安全和合规",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "要验证的SQL语句"
                        }
                    },
                    "required": ["sql"]
                }
            ),
            Tool(
                name="estimate_affected_rows",
                description="预估SQL语句将影响的行数",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "SQL语句"
                        }
                    },
                    "required": ["sql"]
                }
            ),
            Tool(
                name="execute_sql",
                description="执行SQL语句并返回结果（SELECT返回查询结果，UPDATE/INSERT/DELETE返回影响行数）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "要执行的SQL语句"
                        },
                        "params": {
                            "type": "array",
                            "description": "SQL参数（防止SQL注入），可选"
                        }
                    },
                    "required": ["sql"]
                }
            ),
            Tool(
                name="get_server_status",
                description="获取服务器状态和配置信息",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
        
        return ListToolsResult(tools=tools)
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> list:
        """调用工具"""
        try:
            if name == "get_database_schema":
                return await _handle_get_schema(arguments)
            elif name == "generate_sql":
                return await _handle_generate_sql(arguments)
            elif name == "validate_sql":
                return await _handle_validate_sql(arguments)
            elif name == "estimate_affected_rows":
                return await _handle_estimate_rows(arguments)
            elif name == "execute_sql":
                return await _handle_execute_sql(arguments)
            elif name == "get_server_status":
                return await _handle_get_status()
            else:
                return [TextContent(
                    type="text",
                    text=f"Unknown tool: {name}"
                )]
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}", exc_info=True)
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]


async def _handle_get_schema(arguments: Dict[str, Any]) -> list:
    """处理获取Schema请求"""
    table_name = arguments.get("table_name")

    if table_name:
        schema = schema_manager.config_loader.get_table_schema(table_name)
    else:
        schema = await schema_manager.get_full_schema()

    return [TextContent(
        type="text",
        text=json.dumps(schema, ensure_ascii=False, indent=2)
    )]


async def _handle_generate_sql(arguments: Dict[str, Any]) -> list:
    """处理生成SQL请求"""
    query = arguments.get("query", "")
    user_context = arguments.get("user_context", {})

    if not query:
        return [TextContent(
            type="text",
            text="Error: query is required"
        )]

    # 构建提示词
    prompt = _build_sql_prompt(query, user_context)

    # 调用Ollama生成SQL
    ai_response = await ollama_client.generate(prompt)
    logger.info(f"Ollama原始响应: {ai_response[:500]}")  # 记录前500字符用于调试

    # 解析响应
    response_data = _parse_ai_response(ai_response)
    logger.info(f"解析后的response_data: {response_data}")  # 记录解析后的数据

    # 验证SQL
    validation_result = _validate_sql(response_data.get("sql", ""))
    response_data["validation"] = validation_result

    # 评估风险
    response_data["risk_level"] = _evaluate_risk(response_data)

    # 生成优化建议
    sql_type = validation_result.get("sql_type", "")
    suggestions = _generate_suggestions(response_data.get("sql", ""), sql_type)
    if suggestions and "suggestions" not in response_data or not response_data.get("suggestions"):
        response_data["suggestions"] = suggestions
    elif suggestions:
        # 合并AI生成的建议和系统生成的建议
        existing_suggestions = response_data.get("suggestions", [])
        response_data["suggestions"] = list(set(existing_suggestions + suggestions))

    # 返回TextContent列表，让MCP框架包装成CallToolResult
    return [TextContent(
        type="text",
        text=json.dumps(response_data, ensure_ascii=False, indent=2)
    )]


async def _handle_validate_sql(arguments: Dict[str, Any]) -> list:
    """处理SQL验证请求"""
    sql = arguments.get("sql", "")

    validation_result = _validate_sql(sql)

    return [TextContent(
        type="text",
        text=json.dumps(validation_result, ensure_ascii=False, indent=2)
    )]


async def _handle_estimate_rows(arguments: Dict[str, Any]) -> list:
    """处理预估影响行数请求"""
    sql = arguments.get("sql", "")

    estimated_rows = schema_manager.estimate_affected_rows(sql)

    return [TextContent(
        type="text",
        text=json.dumps({
            "estimated_rows": estimated_rows
        }, ensure_ascii=False, indent=2)
    )]


async def _handle_execute_sql(arguments: Dict[str, Any]) -> list:
    """处理SQL执行请求"""
    sql = arguments.get("sql", "")
    params = arguments.get("params")

    # 检查数据库连接
    if not db_connector:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "数据库未配置或连接失败。请在config/server_config.json中设置database.connection_string"
            }, ensure_ascii=False, indent=2)
        )]

    # 验证SQL
    validation_result = _validate_sql(sql)
    if not validation_result.get("is_valid"):
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "SQL验证失败",
                "validation": validation_result
            }, ensure_ascii=False, indent=2)
        )]

    # 执行SQL
    try:
        # 转换参数为tuple
        param_tuple = tuple(params) if params is not None else None

        # 执行SQL
        result = db_connector.execute_sql(sql, param_tuple)

        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]

    except Exception as e:
        logger.error(f"执行SQL失败: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)
        )]


async def _handle_get_status() -> list:
    """处理获取状态请求"""
    config_loader = get_config_loader()

    status = {
        "server": {
            "name": config_loader.get('server.name'),
            "version": config_loader.get('server.version'),
            "description": config_loader.get('server.description'),
            "started_at": datetime.now().isoformat()
        },
        "ollama": {
            "model": config_loader.get('ollama.model'),
            "base_url": config_loader.get('ollama.base_url'),
            "connected": ollama_client.is_connected if ollama_client else False
        },
        "database": {
            "database_name": config_loader.get('database_schema.database_name'),
            "database_type": config_loader.get('database_schema.database_type'),
            "tables_count": len(config_loader.get('database_schema.tables', []))
        }
    }

    return [TextContent(
        type="text",
        text=json.dumps(status, ensure_ascii=False, indent=2)
    )]


def _build_sql_prompt(query: str, user_context: Dict[str, Any]) -> str:
    """构建SQL生成提示词"""
    config_loader = get_config_loader()
    
    prompt_parts = []
    
    # 系统提示词
    prompt_parts.append(config_loader.get('prompts.system_prompt', ''))
    
    # 指令
    prompt_parts.append("\n## 重要规则")
    instructions = config_loader.get('prompts.instructions.general', [])
    for instruction in instructions:
        prompt_parts.append(f"- {instruction}")
    
    # 数据库Schema
    prompt_parts.append("\n" + schema_manager.format_schema_for_prompt())
    
    # 用户上下文
    if user_context:
        prompt_parts.append("\n## 用户上下文")
        prompt_parts.append(f"用户名: {user_context.get('username', 'N/A')}")
        prompt_parts.append(f"角色: {user_context.get('role', 'N/A')}")
        if 'permissions' in user_context:
            prompt_parts.append(f"权限: {', '.join(user_context['permissions'])}")
    
    # 输出格式
    prompt_parts.append("\n## 输出格式要求")
    prompt_parts.append("请严格按照以下JSON格式返回结果：")
    output_format = config_loader.get('prompts.output_format', {})
    prompt_parts.append(json.dumps(output_format, ensure_ascii=False, indent=2))
    
    # 用户查询
    prompt_parts.append(f"\n## 用户查询\n{query}")
    
    return "\n".join(prompt_parts)


def _parse_ai_response(ai_response: str) -> Dict[str, Any]:
    """解析AI响应"""
    import re

    try:
        # 提取JSON部分
        json_start = ai_response.find('{')
        json_end = ai_response.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_str = ai_response[json_start:json_end]
            result = json.loads(json_str)

            # 检查是否有嵌套的template字段（Ollama可能返回这种格式）
            if "template" in result and isinstance(result["template"], dict):
                result = result["template"]

            # 确保必需字段存在
            required_fields = ["sql", "sql_type", "affected_tables", "estimated_rows", "risk_level", "explanation", "require_confirmation"]
            for field in required_fields:
                if field not in result:
                    result[field] = None

            return result
        else:
            raise ValueError("No valid JSON found in AI response")

    except Exception as e:
        logger.error(f"Failed to parse AI response: {e}")
        return {
            "sql": "",
            "sql_type": "UNKNOWN",
            "affected_tables": [],
            "estimated_rows": -1,
            "risk_level": "high",
            "explanation": f"解析AI响应失败: {str(e)}",
            "require_confirmation": True,
            "warnings": ["AI响应解析失败"]
        }


def _validate_sql(sql: str) -> Dict[str, Any]:
    """验证SQL语句"""
    dangerous_keywords = {"DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE", "SHOW", "DESCRIBE"}
    allowed_sql_types = {"SELECT", "UPDATE", "INSERT", "DELETE"}

    result = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "sql_type": None
    }

    # 处理空SQL或None的情况
    if not sql or not isinstance(sql, str):
        result["is_valid"] = False
        result["errors"].append("SQL语句为空或无效")
        return result

    sql_upper = sql.upper().strip()
    
    # 检查危险关键词
    for keyword in dangerous_keywords:
        if keyword in sql_upper:
            result["is_valid"] = False
            result["errors"].append(f"禁止使用 {keyword} 关键词")
    
    if not result["is_valid"]:
        return result
    
    # 检查SQL类型
    sql_type = sql_upper.split()[0] if sql_upper else ""
    if sql_type not in allowed_sql_types:
        result["is_valid"] = False
        result["errors"].append(f"不支持的SQL类型: {sql_type}，仅支持SELECT/UPDATE/INSERT/DELETE")
        return result
    
    result["sql_type"] = sql_type
    
    # DELETE必须包含WHERE
    if sql_type == "DELETE" and "WHERE" not in sql_upper:
        result["is_valid"] = False
        result["errors"].append("DELETE语句必须包含WHERE条件")
        return result
    
    # UPDATE建议包含WHERE
    if sql_type == "UPDATE" and "WHERE" not in sql_upper:
        result["warnings"].append("UPDATE语句建议包含WHERE条件")
    
    # SELECT查询建议避免SELECT *
    if sql_type == "SELECT" and "SELECT *" in sql_upper:
        result["warnings"].append("建议明确指定查询字段，避免使用SELECT *")
    
    # SELECT查询建议添加LIMIT限制
    if sql_type == "SELECT" and "LIMIT" not in sql_upper:
        result["warnings"].append("建议添加LIMIT限制以避免返回过多数据")
    
    # 简单的SQL注入检查
    if ";" in sql or "--" in sql or "/*" in sql:
        result["is_valid"] = False
        result["errors"].append("SQL语句包含可疑字符")
    
    return result


def _evaluate_risk(response_data: Dict[str, Any]) -> str:
    """评估风险等级"""
    sql = response_data.get("sql", "")
    sql_type = response_data.get("sql_type", "")
    estimated_rows = response_data.get("estimated_rows", -1)
    
    # DELETE操作风险最高
    if sql_type == "DELETE":
        return "high" if "WHERE" in sql.upper() else "critical"
    
    # UPDATE操作风险中等偏高
    if sql_type == "UPDATE":
        if estimated_rows > 100:
            return "high"
        elif "WHERE" not in sql.upper():
            return "high"  # 无WHERE的UPDATE风险高
        elif estimated_rows > 10:
            return "medium"
        else:
            return "low"
    
    # INSERT操作风险较低
    if sql_type == "INSERT":
        if estimated_rows > 10:
            return "medium"
        else:
            return "low"
    
    # SELECT操作风险最低（只读）
    if sql_type == "SELECT":
        if estimated_rows > 1000:
            return "medium"  # 可能影响性能
        else:
            return "low"
    
    return "medium"


def _generate_suggestions(sql: str, sql_type: str) -> List[str]:
    """生成SQL优化建议"""
    suggestions = []
    sql_upper = sql.upper()
    
    if sql_type == "SELECT":
        # SELECT优化建议
        if "SELECT *" in sql_upper:
            suggestions.append("建议明确指定查询字段，避免使用SELECT *以减少数据传输量")
        
        if "LIMIT" not in sql_upper:
            suggestions.append("建议添加LIMIT限制以避免返回过多数据影响性能")
        
        if sql_upper.count("JOIN") > 3:
            suggestions.append("多个JOIN可能影响查询性能，建议考虑分批查询或使用缓存")
        
        if "LIKE '%%" in sql_upper:
            suggestions.append("前缀模糊查询（LIKE '%value%'）无法使用索引，建议考虑全文索引")
        
        if sql_upper.count("ORDER BY") > 1:
            suggestions.append("存在多个ORDER BY，建议优化查询结构")
        
        if "GROUP BY" in sql_upper and "HAVING" in sql_upper:
            suggestions.append("HAVING子句效率较低，建议尽可能在WHERE中过滤数据")
        
        if sql_upper.count("DISTINCT") > 0:
            suggestions.append("DISTINCT操作消耗资源，如果可能考虑使用GROUP BY替代")
    
    elif sql_type == "UPDATE":
        # UPDATE优化建议
        if "WHERE" not in sql_upper:
            suggestions.append("UPDATE语句缺少WHERE条件，将更新整表数据，请谨慎确认")
        
        if sql_upper.count(",") > 5:
            suggestions.append("一次更新多个字段，建议确认更新的必要性")
    
    elif sql_type == "DELETE":
        # DELETE优化建议
        if "WHERE" not in sql_upper:
            suggestions.append("DELETE语句缺少WHERE条件，将删除整表数据，非常危险！")
        else:
            suggestions.append("删除操作不可恢复，建议先备份数据或使用软删除（UPDATE status字段）")
    
    elif sql_type == "INSERT":
        # INSERT优化建议
        if "VALUES" in sql_upper and sql_upper.count("VALUES") > 1:
            suggestions.append("批量INSERT效率较高，建议使用批量插入方式")
        
        if "INSERT" in sql_upper and "SELECT" in sql_upper:
            suggestions.append("INSERT INTO ... SELECT语句将复制数据，确认目标表和源表正确")
    
    return suggestions


async def main():
    """启动MCP Server"""
    logger.info("="*60)
    logger.info("Starting db-ai-server MCP Server...")
    logger.info("="*60)
    
    # 初始化服务器
    mcp_server = initialize_server()
    
    # 测试Ollama连接
    try:
        await ollama_client.test_connection()
        logger.info("✓ Ollama connection successful")
    except Exception as e:
        logger.error(f"✗ Failed to connect to Ollama: {e}")
        logger.info("Please ensure Ollama is running: ollama serve")
        return
    
    # 启动服务器
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options()
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
