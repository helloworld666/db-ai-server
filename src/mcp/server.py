"""MCP Server - LangChain v1.0 标准实现

基于LangChain规范的AI数据库SQL生成MCP服务器
"""
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, ListToolsResult, TextContent

from ..config.settings import get_settings
from ..llm.factory import create_llm
from ..schema.manager import SchemaManager
from ..database.connection import DatabaseConnection
from ..security.validator import SQLValidator
from ..prompts.manager import PromptManager
from ..tools.registry import create_database_tools
from ..agents.react_agent import create_react_agent
from ..chains.sql_chain import extract_sql_from_response

logger = logging.getLogger(__name__)


class MCPServer:
    """MCP服务器"""

    def __init__(
        self,
        name: str = "db-ai-server",
        version: str = "7.0.0"
    ):
        self.name = name
        self.version = version
        self.server = Server(name)
        self.schema_manager: Optional[SchemaManager] = None
        self.prompt_manager: Optional[PromptManager] = None
        self.sql_validator: Optional[SQLValidator] = None
        self.db_connection: Optional[DatabaseConnection] = None
        self.db_agent = None
        self.sql_generation_agent = None

    async def initialize(self):
        """初始化服务器组件"""
        setup_logging()
        logger.info("正在初始化MCP服务器 v7.0...")

        settings = get_settings()
        config_path = str(settings.config_dir)

        # 创建管理器（先创建，以便用于显示映射）
        self.schema_manager = SchemaManager(config_path)
        self.prompt_manager = PromptManager(config_path)
        self.sql_validator = SQLValidator(config_path)

        # 创建数据库连接（传入schema_manager用于显示映射）
        db_config = settings.database.connection_string
        if db_config:
            try:
                self.db_connection = DatabaseConnection(db_config, self.schema_manager)
                self.db_connection.test_connection()
                logger.info("数据库连接成功")
            except Exception as e:
                logger.warning(f"数据库连接失败: {e}")
                self.db_connection = None

        # 创建LLM
        llm_config = {
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "api_key": settings.llm.api_key,
            "base_url": settings.llm.base_url,
            "temperature": settings.llm.temperature,
            "max_tokens": settings.llm.max_tokens,
        }
        llm = create_llm(llm_config)

        # 创建工具集
        all_tools = create_database_tools(
            db_connection=self.db_connection,
            schema_manager=self.schema_manager,
            sql_validator=self.sql_validator,
            prompt_manager=self.prompt_manager
        )

        sql_gen_tools = create_database_tools(
            db_connection=None,
            schema_manager=self.schema_manager,
            sql_validator=self.sql_validator,
            prompt_manager=self.prompt_manager,
            include_validate=False
        )

        # 创建Agent
        system_prompt = self.prompt_manager.get_agent_system_prompt()
        max_iterations = self.prompt_manager.get_agent_max_iterations()

        self.db_agent = create_react_agent(
            llm=llm,
            tools=all_tools,
            system_prompt=system_prompt,
            max_iterations=max_iterations
        )

        self.sql_generation_agent = create_react_agent(
            llm=llm,
            tools=sql_gen_tools,
            system_prompt=system_prompt,
            max_iterations=max_iterations
        )

        logger.info(f"MCP服务器初始化完成")

    def register_tools(self):
        """注册MCP工具"""

        @self.server.list_tools()
        async def list_tools() -> ListToolsResult:
            """列出所有可用工具"""
            # 从prompt_manager获取工具描述
            get_schema_desc = self.prompt_manager.get_tool_description("get_database_schema")
            dql_desc = self.prompt_manager.get_tool_description("execute_dql")
            dml_desc = self.prompt_manager.get_tool_description("execute_dml")
            validate_desc = self.prompt_manager.get_tool_description("validate_sql")
            status_desc = self.prompt_manager.get_tool_description("get_server_status")

            # 从prompt_manager获取参数描述
            get_schema_params = self.prompt_manager.get_tool_param_description("get_database_schema")
            dql_params = self.prompt_manager.get_tool_param_description("execute_dql")
            dml_params = self.prompt_manager.get_tool_param_description("execute_dml")
            validate_params = self.prompt_manager.get_tool_param_description("validate_sql")

            tools = [
                Tool(
                    name="get_database_schema",
                    description=get_schema_desc or "获取数据库Schema信息",
                    inputSchema={
                        "type": "object",
                        "properties": {"table_name": {"type": "string", "description": get_schema_params.get("table_name", "可选，表名")}},
                    }
                ),
                Tool(
                    name="execute_dql",
                    description=dql_desc or "【仅查询】执行SELECT查询",
                    inputSchema={
                        "type": "object",
                        "properties": {"sql": {"type": "string", "description": dql_params.get("sql", "SELECT查询语句")}},
                        "required": ["sql"]
                    }
                ),
                Tool(
                    name="execute_dml",
                    description=dml_desc or "【数据修改】执行INSERT/UPDATE/DELETE",
                    inputSchema={
                        "type": "object",
                        "properties": {"sql": {"type": "string", "description": dml_params.get("sql", "INSERT/UPDATE/DELETE语句")}},
                        "required": ["sql"]
                    }
                ),
                Tool(
                    name="validate_sql",
                    description=validate_desc or "验证SQL安全性",
                    inputSchema={
                        "type": "object",
                        "properties": {"sql": {"type": "string", "description": validate_params.get("sql", "SQL语句")}},
                        "required": ["sql"]
                    }
                ),
                Tool(
                    name="get_server_status",
                    description=status_desc or "获取服务器状态",
                    inputSchema={"type": "object", "properties": {}}
                )
            ]
            return ListToolsResult(tools=tools)

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> list:
            """调用工具"""
            logger.info(f"收到工具调用请求: {name}, 参数: {arguments}")
            try:
                if name == "get_database_schema":
                    table_name = arguments.get("table_name")
                    if table_name:
                        schema = self.schema_manager.get_table_schema(table_name)
                        if schema is None:
                            return [TextContent(type="text", text=json.dumps({"success": False, "error": f"表 '{table_name}' 不存在"}, ensure_ascii=False))]
                        return [TextContent(type="text", text=json.dumps(schema, ensure_ascii=False, indent=2))]
                    else:
                        schema = self.schema_manager.get_full_schema()
                        return [TextContent(type="text", text=json.dumps(schema, ensure_ascii=False, indent=2))]

                elif name == "generate_sql":
                    query = arguments.get("query", "")
                    if not query:
                        return [TextContent(type="text", text=json.dumps({"success": False, "error": "query参数不能为空"}, ensure_ascii=False))]

                    result = await self.sql_generation_agent.ainvoke(query=query)

                    if result.get("success"):
                        agent_result = result.get("result", "")
                        logger.info(f"Agent返回结果: {repr(agent_result)}")

                        sql_list = extract_sql_from_response(agent_result)
                        logger.info(f"提取到SQL列表: {sql_list}")

                        if sql_list:
                            return [TextContent(type="text", text=json.dumps({"success": True, "sql_list": sql_list}, ensure_ascii=False))]
                        else:
                            return [TextContent(type="text", text=json.dumps({"success": False, "error": "未能从响应中提取SQL语句", "agent_response": agent_result[:500]}, ensure_ascii=False))]
                    else:
                        return [TextContent(type="text", text=json.dumps({"success": False, "error": result.get("error", "生成SQL失败")}, ensure_ascii=False))]

                elif name == "validate_sql":
                    sql = arguments.get("sql", "")
                    result = self.sql_validator.validate(sql)
                    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

                elif name == "execute_dql":
                    if not self.db_connection:
                        return [TextContent(type="text", text=json.dumps({"success": False, "error": "数据库未配置或连接失败"}, ensure_ascii=False))]

                    sql = arguments.get("sql", "")
                    logger.info(f"[DQL查询] {sql}")
                    validation = self.sql_validator.validate(sql)
                    if not validation.get("is_valid"):
                        return [TextContent(type="text", text=json.dumps({"success": False, "error": "SQL验证失败", "validation": validation}, ensure_ascii=False))]

                    result = self.db_connection.execute_query(sql)
                    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

                elif name == "execute_dml":
                    if not self.db_connection:
                        return [TextContent(type="text", text=json.dumps({"success": False, "error": "数据库未配置或连接失败"}, ensure_ascii=False))]

                    sql = arguments.get("sql", "")
                    logger.info(f"[DML执行] {sql}")
                    validation = self.sql_validator.validate(sql)
                    if not validation.get("is_valid"):
                        return [TextContent(type="text", text=json.dumps({"success": False, "error": "SQL验证失败", "validation": validation}, ensure_ascii=False))]

                    result = self.db_connection.execute_update(sql)
                    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

                elif name == "get_server_status":
                    settings = get_settings()
                    status = {
                        "server": {"name": "db-ai-server", "version": "7.0.0", "architecture": "langchain_v1"},
                        "llm": {"provider": settings.llm.provider, "model": settings.llm.model},
                        "database": {"connected": self.db_connection is not None, "tables_count": len(self.schema_manager.get_all_table_names()) if self.schema_manager else 0}
                    }
                    return [TextContent(type="text", text=json.dumps(status, ensure_ascii=False, indent=2))]

                else:
                    return [TextContent(type="text", text=f"未知工具: {name}")]

            except Exception as e:
                logger.error(f"工具执行失败 {name}: {e}")
                return [TextContent(type="text", text=json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))]

    async def run(self):
        """运行服务器"""
        await self.initialize()
        self.register_tools()

        logger.info("=" * 60)
        logger.info("Starting DB-AI-Server MCP Server v7.0")
        logger.info("=" * 60)

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def create_mcp_server() -> MCPServer:
    """创建MCP服务器实例"""
    return MCPServer()


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

    logging.getLogger("src.llm").setLevel(logging.DEBUG)
    logging.getLogger("src.agents").setLevel(logging.DEBUG)
    logging.getLogger("src.schema").setLevel(logging.DEBUG)
