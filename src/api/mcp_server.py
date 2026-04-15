"""MCP服务器 - 基于新架构"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, ListToolsResult, TextContent

from ..core.config.settings import get_settings
from ..llm.factory import LLMFactory
from ..database.connection import DatabaseConnection
from ..database.schema import SchemaManager
from ..database.prompts import PromptManager
from ..security.validator import SQLValidator
from ..agents.sql_agent import SQLAgent
from ..tools.db_tools import create_database_tools

logger = logging.getLogger(__name__)

mcp_server = Server("db-ai-server")

schema_manager: Optional[SchemaManager] = None
prompt_manager: Optional[PromptManager] = None
sql_validator: Optional[SQLValidator] = None
db_connection: Optional[DatabaseConnection] = None
db_agent: Optional[SQLAgent] = None
ai_client: Optional[Any] = None


def setup_logging():
    """配置日志"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'mcp_server.log', encoding='utf-8'),
            logging.StreamHandler(sys.stderr)
        ]
    )


async def initialize():
    """初始化组件"""
    global schema_manager, prompt_manager, sql_validator, db_connection, db_agent, ai_client

    setup_logging()
    logger.info("正在初始化MCP服务器...")

    settings = get_settings()
    config_path = str(settings.config_dir)

    db_config = settings.database.connection_string
    if db_config:
        try:
            db_connection = DatabaseConnection(db_config)
            db_connection.test_connection()
            logger.info("数据库连接成功")
        except Exception as e:
            logger.warning(f"数据库连接失败: {e}")
            db_connection = None

    schema_manager = SchemaManager(config_path)
    prompt_manager = PromptManager(config_path)
    sql_validator = SQLValidator(config_path)

    try:
        from ..database.llm_client import get_ai_client
        ai_client = get_ai_client(settings)
    except ImportError:
        ai_client = None

    llm_config = {
        "provider": settings.llm.provider,
        "model": settings.llm.model,
        "api_key": settings.llm.api_key,
        "base_url": settings.llm.base_url,
        "temperature": settings.llm.temperature,
        "max_tokens": settings.llm.max_tokens,
    }

    llm = LLMFactory.create(llm_config, existing_client=ai_client)

    tools = create_database_tools(
        db_connection=db_connection,
        schema_manager=schema_manager,
        prompt_manager=prompt_manager,
        sql_validator=sql_validator,
        llm_client=ai_client
    )

    db_agent = SQLAgent(
        llm=llm,
        tools=tools,
        schema_manager=schema_manager,
        prompt_manager=prompt_manager,
        sql_validator=sql_validator
    )

    logger.info(f"MCP服务器初始化完成，工具数量: {len(tools)}")


def register_tools():
    """注册MCP工具"""

    @mcp_server.list_tools()
    async def list_tools() -> ListToolsResult:
        tools = [
            Tool(
                name="get_database_schema",
                description="获取数据库Schema信息（表结构、字段、说明）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "可选，指定表名"
                        }
                    }
                }
            ),
            Tool(
                name="generate_sql",
                description="根据自然语言生成SQL语句",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "用户自然语言描述"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="validate_sql",
                description="验证SQL语句安全性",
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
                name="execute_sql",
                description="执行SQL语句",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "要执行的SQL语句"
                        }
                    },
                    "required": ["sql"]
                }
            ),
            Tool(
                name="get_server_status",
                description="获取服务器状态",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
        return ListToolsResult(tools=tools)

    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> list:
        try:
            if name == "get_database_schema":
                table_name = arguments.get("table_name")
                schema = schema_manager.get_full_schema() if not table_name else schema_manager.get_table_schema(table_name)
                return [TextContent(type="text", text=json.dumps(schema, ensure_ascii=False, indent=2))]

            elif name == "generate_sql":
                query = arguments.get("query", "")
                result = await db_agent.ainvoke(query=query)
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

            elif name == "validate_sql":
                sql = arguments.get("sql", "")
                result = sql_validator.validate(sql)
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

            elif name == "execute_sql":
                if not db_connection:
                    return [TextContent(type="text", text=json.dumps({
                        "success": False,
                        "error": "数据库未配置"
                    }, ensure_ascii=False))]

                sql = arguments.get("sql", "")
                validation = sql_validator.validate(sql)
                if not validation.get("is_valid"):
                    return [TextContent(type="text", text=json.dumps({
                        "success": False,
                        "error": "SQL验证失败",
                        "validation": validation
                    }, ensure_ascii=False))]

                result = db_connection.execute_sql(sql, None)
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

            elif name == "get_server_status":
                status = {
                    "server": {
                        "name": "db-ai-server",
                        "version": "2.0.0"
                    },
                    "agent": db_agent.get_status() if db_agent else None,
                    "database": {
                        "connected": db_connection is not None,
                        "tables_count": len(schema_manager.get_all_table_names()) if schema_manager else 0
                    }
                }
                return [TextContent(type="text", text=json.dumps(status, ensure_ascii=False, indent=2))]

            else:
                return [TextContent(type="text", text=f"未知工具: {name}")]

        except Exception as e:
            logger.error(f"工具执行失败 {name}: {e}")
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False))]


async def main():
    """启动MCP服务器"""
    await initialize()
    register_tools()

    logger.info("=" * 60)
    logger.info("Starting DB-AI-Server MCP Server v2.0")
    logger.info("=" * 60)

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
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器错误: {e}")
        sys.exit(1)
