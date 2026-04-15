#!/usr/bin/env python3
"""
DB-AI-Server MCP Server v2.0
基于LangChain + LangGraph的AI数据库SQL生成服务器

核心原则：
1. 所有配置从JSON文件读取，禁止硬编码
2. 所有提示词从配置文件读取，禁止硬编码
3. 工具调用完全由LLM自主决定
4. 数据库Schema从配置文件动态加载
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, ListToolsResult, TextContent

# 添加src到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config.settings import get_settings
from src.llm.factory import LLMFactory
from src.database.connection import DatabaseConnection
from src.database.schema import SchemaManager
from src.database.prompts import PromptManager
from src.database.llm_client import get_ai_client
from src.security.validator import SQLValidator
from src.agents.sql_agent import SQLAgent
from src.tools.db_tools import create_database_tools, _apply_display_mapping

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
    logger.info("正在初始化MCP服务器 v2.0...")

    # 加载设置
    settings = get_settings()
    config_path = str(settings.config_dir)

    # 创建数据库连接
    db_config = settings.database.connection_string
    if db_config:
        try:
            db_connection = DatabaseConnection(db_config)
            db_connection.test_connection()
            logger.info("数据库连接成功")
        except Exception as e:
            logger.warning(f"数据库连接失败: {e}")
            db_connection = None
    else:
        logger.info("未配置数据库连接，SQL执行功能将不可用")

    # 创建管理器（从配置文件加载）
    schema_manager = SchemaManager(config_path)
    prompt_manager = PromptManager(config_path)
    sql_validator = SQLValidator(config_path)

    # 获取AI客户端（复用现有客户端实现）
    ai_client = get_ai_client(settings)

    # 创建LLM（LangChain兼容）
    llm_config = {
        "provider": settings.llm.provider,
        "model": settings.llm.model,
        "api_key": settings.llm.api_key,
        "base_url": settings.llm.base_url,
        "temperature": settings.llm.temperature,
        "max_tokens": settings.llm.max_tokens,
    }

    llm = LLMFactory.create(llm_config, existing_client=ai_client)

    # 创建工具（由LLM自主决定调用）
    tools = create_database_tools(
        db_connection=db_connection,
        schema_manager=schema_manager,
        prompt_manager=prompt_manager,
        sql_validator=sql_validator,
        llm_client=ai_client
    )

    # 创建Agent
    db_agent = SQLAgent(
        llm=llm,
        tools=tools,
        schema_manager=schema_manager,
        prompt_manager=prompt_manager,
        sql_validator=sql_validator
    )

    logger.info(f"MCP服务器初始化完成")
    logger.info(f"  - 工具数量: {len(tools)}")
    logger.info(f"  - LLM: {settings.llm.provider}/{settings.llm.model}")
    logger.info(f"  - 数据库: {settings.database.connection_string and '已配置' or '未配置'}")


def register_tools():
    """注册MCP工具"""

    @mcp_server.list_tools()
    async def list_tools() -> ListToolsResult:
        """列出所有可用工具"""
        tools = [
            Tool(
                name="get_database_schema",
                description="获取数据库Schema信息（表结构、字段、说明）。无参数时返回所有表的信息。",
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
                description="根据自然语言描述生成SQL语句（SELECT/UPDATE/INSERT/DELETE）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "用户自然语言描述，例如：查询所有用户；修改某用户状态"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="validate_sql",
                description="验证SQL语句是否安全和合规",
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

    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> list:
        """调用工具"""
        try:
            if name == "get_database_schema":
                table_name = arguments.get("table_name")
                if table_name:
                    schema = schema_manager.get_table_schema(table_name)
                    if schema is None:
                        return [TextContent(type="text", text=json.dumps({
                            "success": False,
                            "error": f"表 '{table_name}' 不存在"
                        }, ensure_ascii=False))]
                    return [TextContent(type="text", text=json.dumps(schema, ensure_ascii=False, indent=2))]
                else:
                    schema = schema_manager.get_full_schema()
                    return [TextContent(type="text", text=json.dumps(schema, ensure_ascii=False, indent=2))]

            elif name == "generate_sql":
                query = arguments.get("query", "")
                if not query:
                    return [TextContent(type="text", text=json.dumps({
                        "success": False,
                        "error": "query参数不能为空"
                    }, ensure_ascii=False))]

                # 使用Agent处理（LLM自主决定工具调用）
                result = await db_agent.ainvoke(query=query)
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

            elif name == "validate_sql":
                sql = arguments.get("sql", "")
                result = sql_validator.validate(sql)
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

            elif name == "estimate_affected_rows":
                sql = arguments.get("sql", "")
                estimated_rows = schema_manager.estimate_affected_rows(sql)
                return [TextContent(type="text", text=json.dumps({
                    "estimated_rows": estimated_rows
                }, ensure_ascii=False))]

            elif name == "execute_sql":
                if not db_connection:
                    return [TextContent(type="text", text=json.dumps({
                        "success": False,
                        "error": "数据库未配置或连接失败"
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
                # 应用 display_mapping 转换
                result = _apply_display_mapping(result, sql, schema_manager)
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

            elif name == "get_server_status":
                settings = get_settings()
                status = {
                    "server": {
                        "name": "db-ai-server",
                        "version": "2.0.0",
                        "architecture": "langchain_v2"
                    },
                    "llm": {
                        "provider": settings.llm.provider,
                        "model": settings.llm.model
                    },
                    "database": {
                        "connected": db_connection is not None,
                        "tables_count": len(schema_manager.get_all_table_names()) if schema_manager else 0
                    },
                    "agent": db_agent.get_status() if db_agent else None
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
