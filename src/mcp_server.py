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
    from mcp.types import (Tool, ListToolsResult, TextContent, )
except ImportError:
    print("错误: 未安装mcp包，请运行: pip install mcp")
    sys.exit(1)

from src.config_loader import get_config_loader
from src.ollama_client import OllamaClient
from src.lmstudio_client import LMStudioClient
from src.cloud_ai_client import CloudAIClient
from src.schema_manager import SchemaManager
from src.database_connector import DatabaseConnector
from src.agent_wrapper import AgentWrapper


# 配置日志
def setup_logging():
    """配置日志系统"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_dir / 'mcp_server.log', encoding='utf-8'), logging.StreamHandler(sys.stderr)
            # 输出到stderr，避免干扰MCP协议通信
        ])


setup_logging()
logger = logging.getLogger(__name__)

# 全局变量
server: Optional[Server] = None
ollama_client: Optional[OllamaClient] = None
lmstudio_client: Optional[LMStudioClient] = None
cloud_client: Optional[CloudAIClient] = None
ai_client = None  # 通用的 AI 客户端（OllamaClient 或 LMStudioClient 或 CloudAIClient）
schema_manager: Optional[SchemaManager] = None
db_connector: Optional[DatabaseConnector] = None
agent_wrapper: Optional[AgentWrapper] = None


def initialize_server():
    """初始化服务器组件"""
    global server, ollama_client, lmstudio_client, cloud_client, ai_client, schema_manager, db_connector, agent_wrapper

    # 加载配置
    logger.info("Initializing db-ai-server MCP Server...")

    config_loader = get_config_loader()

    # 获取推理引擎配置（统一配置）
    engine_config = config_loader.get_inference_config()
    engine_type = engine_config.get('type', 'lmstudio')
    logger.info(f"Using inference engine: {engine_type}")

    # 云端AI平台列表
    cloud_platforms = ['deepseek', 'qwen', 'zhipu', 'openai', 'claude']
    
    if engine_type in cloud_platforms:
        # 云端AI平台 - 从云端配置或内联配置中获取
        api_key = engine_config.get('api_key', '')
        
        # 如果主配置中没有API Key，尝试从cloud_platforms.json中获取
        if not api_key:
            platform_config = config_loader.get_cloud_platform_config(engine_type)
            api_key = platform_config.get('api_key', '')
        
        if not api_key:
            logger.error(f"{engine_type} requires API key. Please set 'api_key' in config.")
            raise ValueError(f"Missing API key for {engine_type}")
        
        # 合并配置：优先使用主配置，其次使用平台配置文件
        base_url = engine_config.get('base_url')
        model = engine_config.get('model')
        
        if not base_url or not model:
            platform_config = config_loader.get_cloud_platform_config(engine_type)
            base_url = base_url or platform_config.get('base_url')
            model = model or platform_config.get('model')
        
        logger.info(f"Platform: {engine_type}")
        logger.info(f"Base URL: {base_url}")
        logger.info(f"Model: {model}")
        
        cloud_client = CloudAIClient(
            platform=engine_type,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=engine_config.get('timeout', 120),
            max_retries=engine_config.get('max_retries', 3)
        )
        ai_client = cloud_client
        
    elif engine_type == 'lmstudio':
        # 初始化 LM Studio 客户端
        logger.info(f"Base URL: {engine_config.get('base_url')}")
        logger.info(f"Model: {engine_config.get('model')}")
        lmstudio_client = LMStudioClient(base_url=engine_config.get('base_url'), model=engine_config.get('model'),
            timeout=engine_config.get('timeout', 120), max_retries=engine_config.get('max_retries', 3))
        ai_client = lmstudio_client

    else:
        # 默认使用 Ollama 客户端
        logger.info(f"Base URL: {engine_config.get('base_url')}")
        logger.info(f"Model: {engine_config.get('model')}")
        ollama_client = OllamaClient(base_url=engine_config.get('base_url'), model=engine_config.get('model'),
            timeout=engine_config.get('timeout', 120), max_retries=engine_config.get('max_retries', 3))
        ai_client = ollama_client

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

    # 初始化智能代理
    try:
        agent_wrapper = AgentWrapper(config_loader)
        agent_initialized = agent_wrapper.initialize()
        if agent_initialized:
            logger.info("智能代理初始化成功")
        else:
            logger.warning("智能代理初始化失败，智能执行功能可能受限")
    except Exception as e:
        logger.warning(f"智能代理初始化异常: {e}")
        agent_wrapper = None

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
        tools = [Tool(name="get_database_schema", description="获取数据库Schema信息（表结构、字段、说明）",
            inputSchema={"type": "object",
                "properties": {"table_name": {"type": "string", "description": "可选，指定表名以获取特定表的Schema"}}}),
            Tool(name="generate_sql", description="根据自然语言描述生成SELECT/UPDATE/INSERT/DELETE SQL语句",
                inputSchema={"type": "object", "properties": {"query": {"type": "string",
                    "description": "用户自然语言描述，例如：查询所有激活的用户；修改用户表，将所有未激活用户的status字段改为active"},
                    "user_context": {"type": "object", "description": "用户上下文信息（可选）",
                        "properties": {"username": {"type": "string"}, "role": {"type": "string"},
                            "permissions": {"type": "array", "items": {"type": "string"}}}}}, "required": ["query"]}),
            Tool(name="validate_sql", description="验证生成的SQL语句是否安全和合规", inputSchema={"type": "object",
                "properties": {"sql": {"type": "string", "description": "要验证的SQL语句"}}, "required": ["sql"]}),
            Tool(name="estimate_affected_rows", description="预估SQL语句将影响的行数",
                inputSchema={"type": "object", "properties": {"sql": {"type": "string", "description": "SQL语句"}},
                    "required": ["sql"]}),             Tool(name="execute_sql",
                description="执行SQL语句并返回结果（SELECT返回查询结果，UPDATE/INSERT/DELETE返回影响行数）",
                inputSchema={"type": "object",
                    "properties": {"sql": {"type": "string", "description": "要执行的SQL语句"},
                        "params": {"type": "array", "description": "SQL参数（防止SQL注入），可选"}}, "required": ["sql"]}),
            Tool(name="execute_intelligently",
                description="智能执行：AI自主分析用户意图，自动规划多步操作（数据变更后自动验证）",
                inputSchema={"type": "object",
                    "properties": {"query": {"type": "string", "description": "用户自然语言描述"},
                        "user_context": {"type": "object", "description": "用户上下文信息（可选）",
                            "properties": {"username": {"type": "string"}, "role": {"type": "string"},
                                "permissions": {"type": "array", "items": {"type": "string"}}}}}, "required": ["query"]}),
            Tool(name="get_server_status", description="获取服务器状态和配置信息",
                inputSchema={"type": "object", "properties": {}})]

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
            elif name == "execute_intelligently":
                return await _handle_execute_intelligently(arguments)
            elif name == "get_server_status":
                return await _handle_get_status()
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _handle_get_schema(arguments: Dict[str, Any]) -> list:
    """处理获取Schema请求"""
    table_name = arguments.get("table_name")

    if table_name:
        schema = schema_manager.config_loader.get_table_schema(table_name)
    else:
        schema = await schema_manager.get_full_schema()

    return [TextContent(type="text", text=json.dumps(schema, ensure_ascii=False, indent=2))]


async def _handle_generate_sql(arguments: Dict[str, Any]) -> list:
    """处理生成SQL请求"""
    query = arguments.get("query", "")
    user_context = arguments.get("user_context", {})

    if not query:
        return [TextContent(type="text", text="Error: query is required")]

    # 构建提示词
    prompt = _build_sql_prompt(query, user_context)

    # 调用AI生成SQL
    ai_response = await ai_client.generate(prompt)
    logger.info(f"AI原始响应: {ai_response[:500]}")

    # 解析响应
    response_data = _parse_ai_response(ai_response)
    logger.info(f"解析后的response_data: {response_data}")

    # 检查SQL中是否包含占位符（排除 LIKE 的 % 通配符）
    import re
    sql = response_data.get("sql", "")
    if sql:
        # 只检测真正的参数占位符
        placeholder_pattern = r'(\?|%\d*[sdfe]|%\([^)]+\)|\$\d|\bparam\d*\b)'
        if re.search(placeholder_pattern, sql, re.IGNORECASE):
            logger.error(f"AI生成的SQL包含占位符，这是不允许的")
            # 生成友好的错误提示
            error_msg = "数据库操做描述不够具体。请提供更明确的描述，例如：\n"
            error_msg += "- '更新货架编号为***的货架,将其编号更改为***'\n"
            error_msg += "- '更新用户名为***的用户为可用状态'"
            response_data["sql"] = ""
            response_data["error"] = error_msg
            response_data["explanation"] = error_msg
            response_data["risk_level"] = "high"
            return [TextContent(type="text", text=json.dumps(response_data, ensure_ascii=False, indent=2))]

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
        existing_suggestions = response_data.get("suggestions", [])
        response_data["suggestions"] = list(set(existing_suggestions + suggestions))

    return [TextContent(type="text", text=json.dumps(response_data, ensure_ascii=False, indent=2))]


async def _handle_validate_sql(arguments: Dict[str, Any]) -> list:
    """处理SQL验证请求"""
    sql = arguments.get("sql", "")

    validation_result = _validate_sql(sql)

    return [TextContent(type="text", text=json.dumps(validation_result, ensure_ascii=False, indent=2))]


async def _handle_estimate_rows(arguments: Dict[str, Any]) -> list:
    """处理预估影响行数请求"""
    sql = arguments.get("sql", "")

    estimated_rows = schema_manager.estimate_affected_rows(sql)

    return [TextContent(type="text", text=json.dumps({"estimated_rows": estimated_rows}, ensure_ascii=False, indent=2))]


async def _handle_execute_sql(arguments: Dict[str, Any]) -> list:
    """处理SQL执行请求"""
    sql = arguments.get("sql", "")
    params = arguments.get("params")

    # 检查数据库连接
    if not db_connector:
        return [TextContent(type="text", text=json.dumps({"success": False,
            "error": "数据库未配置或连接失败。请在config/server_config.json中设置database.connection_string"},
            ensure_ascii=False, indent=2))]

    # 验证SQL
    validation_result = _validate_sql(sql)
    if not validation_result.get("is_valid"):
        return [TextContent(type="text",
            text=json.dumps({"success": False, "error": "SQL验证失败", "validation": validation_result},
                ensure_ascii=False, indent=2))]

    # 执行SQL
    try:
        # 执行SQL（SQL应该已经包含实际值，不需要params）
        result = db_connector.execute_sql(sql, None)

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    except Exception as e:
        logger.error(f"执行SQL失败: {e}")
        return [TextContent(type="text",
            text=json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2))]


async def _handle_execute_intelligently(arguments: Dict[str, Any]) -> list:
    """处理智能执行请求：AI自主分析用户意图并规划多步操作 - 使用智能代理"""
    query = arguments.get("query", "")
    user_context = arguments.get("user_context", {})

    if not query:
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": "query参数不能为空"
        }, ensure_ascii=False, indent=2))]

    # TODO: 暂时禁用智能代理，因为有异步事件循环问题
    # 问题: asyncio.run() cannot be called from a running event loop
    # 解决方案: 暂时强制使用回退逻辑，确保系统可用
    logger.warning("智能代理有异步事件循环问题，暂时使用回退逻辑")
    return await _handle_execute_intelligently_fallback(arguments)

async def _handle_execute_intelligently_fallback(arguments: Dict[str, Any]) -> list:
    """智能执行的回退逻辑（原始实现）"""
    query = arguments.get("query", "")
    user_context = arguments.get("user_context", {})

    # 检查数据库连接
    if not db_connector:
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": "数据库未配置或连接失败。请在config/server_config.json中设置database.connection_string"
        }, ensure_ascii=False, indent=2))]

    try:
        # 1. 生成SQL（AI会根据原则判断是否需要多步操作）
        sql_generation_result = await _handle_generate_sql({
            "query": query,
            "user_context": user_context
        })
        
        # 解析生成的SQL结果
        sql_result_text = sql_generation_result[0].text
        sql_result = json.loads(sql_result_text)
        
        # 检查是否生成成功
        if "error" in sql_result and sql_result["error"]:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": sql_result["error"],
                "explanation": sql_result.get("explanation", "")
            }, ensure_ascii=False, indent=2))]
        
        # 获取SQL信息
        main_sql = sql_result.get("sql", "")
        follow_up_sql = sql_result.get("follow_up_sql", "")
        requires_verification = sql_result.get("requires_verification", False)
        sql_type = sql_result.get("sql_type", "").upper()
        
        # 调试日志：查看AI生成的验证SQL
        logger.info(f"智能执行调试 - AI生成的验证SQL: '{follow_up_sql}'")
        logger.info(f"智能执行调试 - 是否需要验证: {requires_verification}")
        
        if not main_sql:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": "未能生成有效的SQL语句",
                "explanation": sql_result.get("explanation", "")
            }, ensure_ascii=False, indent=2))]
        
        # 2. 验证主SQL
        validation_result = _validate_sql(main_sql)
        if not validation_result.get("is_valid"):
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": "SQL验证失败",
                "validation": validation_result,
                "sql": main_sql
            }, ensure_ascii=False, indent=2))]
        
        # 3. 执行SQL
        logger.info(f"智能执行(回退) - 主SQL: {main_sql}")
        logger.info(f"是否需要验证: {requires_verification}, 验证SQL: '{follow_up_sql}'")
        logger.info(f"验证SQL不为空: {bool(follow_up_sql and follow_up_sql.strip())}")
        logger.info(f"是否满足多步执行条件: {requires_verification and bool(follow_up_sql and follow_up_sql.strip())}")
        
        # 强制调试：确保验证查询被执行
        if sql_type == "INSERT" and not follow_up_sql.strip():
            # 如果AI没有生成验证查询，自动生成一个
            logger.warning("AI没有生成验证查询，自动生成一个")
            # 获取表名
            import re
            table_match = re.search(r'INSERT\s+INTO\s+(\w+)', main_sql, re.IGNORECASE)
            if table_match:
                table_name = table_match.group(1)
                # 如果表名是sys_user，生成验证查询
                if table_name.lower() == "sys_user":
                    # 找到用户名
                    name_match = re.search(r"VALUES\s*\([^)]*'([^']+)'[^)]*\)", main_sql)
                    if name_match:
                        username = name_match.group(1)
                        follow_up_sql = f"SELECT * FROM {table_name} WHERE name = '{username}'"
                        requires_verification = True
                        logger.info(f"自动生成的验证查询: {follow_up_sql}")
        
        # 如果有验证查询，使用多步执行
        if requires_verification and follow_up_sql and follow_up_sql.strip():
            logger.info(f"回退逻辑: 执行多步SQL，主SQL: {main_sql[:100]}..., 验证SQL: {follow_up_sql[:100]}...")
            # 使用多步执行
            multi_step_result = db_connector.execute_multi_step_sql(main_sql, follow_up_sql, None)
            logger.info(f"回退逻辑: 多步执行结果类型: {type(multi_step_result)}")
            logger.info(f"回退逻辑: 多步执行结果 - success: {multi_step_result.get('success')}")
            logger.info(f"回退逻辑: 主执行结果: {multi_step_result.get('main_execution')}")
            logger.info(f"回退逻辑: 验证执行结果: {multi_step_result.get('follow_up_execution')}")
            
            # 检查主SQL是否成功（主SQL失败会导致整个操作失败）
            main_execution = multi_step_result.get("main_execution")
            if not main_execution or not main_execution.get("success", False):
                return [TextContent(type="text", text=json.dumps({
                    "success": False,
                    "error": multi_step_result.get("error", "主SQL执行失败"),
                    "sql": main_sql
                }, ensure_ascii=False, indent=2))]
            
            # 准备返回结果
            combined_result = {
                "success": True,  # 主SQL成功就是成功
                "sql_generation": sql_result,
                "main_execution": main_execution,
                "follow_up_execution": multi_step_result.get("follow_up_execution"),
                "execution_mode": "multi_step_with_verification",
                "overall_status": "main_sql_success"
            }
            
            # 处理验证结果
            follow_up_execution = multi_step_result.get("follow_up_execution")
            if follow_up_execution:
                if follow_up_execution.get("success", False):
                    if follow_up_execution.get("verification_status") == "no_data_found":
                        combined_result["overall_status"] = "main_success_verification_no_data"
                        combined_result["warning"] = "主SQL执行成功，但验证查询未找到匹配的数据"
                    else:
                        combined_result["overall_status"] = "main_success_verification_success"
                else:
                    combined_result["overall_status"] = "main_success_verification_failed"
                    combined_result["warning"] = follow_up_execution.get("warning", "主SQL执行成功，但验证查询失败")
            
            combined_result["explanation"] = f"AI检测到这是数据变更操作。{sql_result.get('explanation', '')}"
            
            # 如果主SQL是INSERT且有自增ID，在结果中添加
            if main_execution and sql_type == "INSERT" and main_execution.get("insert_id"):
                combined_result["inserted_id"] = main_execution["insert_id"]
                
        else:
            # 单步执行（不需要验证或没有验证SQL）
            main_result = db_connector.execute_sql(main_sql, None)
            
            if not main_result.get("success", False):
                return [TextContent(type="text", text=json.dumps({
                    "success": False,
                    "error": main_result.get("error", "执行SQL失败"),
                    "sql": main_sql
                }, ensure_ascii=False, indent=2))]
            
            combined_result = {
                "success": True,
                "sql_generation": sql_result,
                "main_execution": main_result,
                "follow_up_execution": None,
                "execution_mode": "single_step",
                "explanation": sql_result.get("explanation", "")
            }
        
        return [TextContent(type="text", text=json.dumps(combined_result, ensure_ascii=False, indent=2))]
    
    except Exception as e:
        logger.error(f"智能执行(回退)失败: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2))]


async def _handle_get_status() -> list:
    """处理获取状态请求"""
    config_loader = get_config_loader()

    status = {"server": {"name": config_loader.get('server.name'), "version": config_loader.get('server.version'),
        "description": config_loader.get('server.description'), "started_at": datetime.now().isoformat()},
        "inference_engine": config_loader.get_inference_config(),
        "database": {"database_name": config_loader.get('database_schema.database_name'),
            "database_type": config_loader.get('database_schema.database_type'),
            "tables_count": len(config_loader.get('database_schema.tables', []))}}

    # 添加连接状态
    if 'inference_engine' in status:
        status['inference_engine']['connected'] = ai_client.is_connected if ai_client else False

    return [TextContent(type="text", text=json.dumps(status, ensure_ascii=False, indent=2))]


def _build_sql_prompt(query: str, user_context: Dict[str, Any]) -> str:
    """构建SQL生成提示词"""
    config_loader = get_config_loader()
    prompts_config = config_loader.get_prompts_config()
    instructions = prompts_config.get('instructions', {})

    prompt_parts = []

    # 系统提示词
    prompt_parts.append(prompts_config.get('system_prompt', ''))

    # 核心规则
    core_rules = instructions.get('core_rules', [])
    if core_rules:
        prompt_parts.append("\n核心规则:")
        for rule in core_rules:
            prompt_parts.append(f"- {rule}")

    # 查询规则
    select_rules = instructions.get('select_rules', [])
    if select_rules:
        prompt_parts.append("\n查询规则:")
        for rule in select_rules:
            prompt_parts.append(f"- {rule}")

    # 操作原则
    operation_principles = instructions.get('operation_principles', [])
    if operation_principles:
        prompt_parts.append("\n操作原则:")
        for principle in operation_principles:
            prompt_parts.append(f"- {principle}")

    # 输出格式
    prompt_parts.append("\n输出JSON:")
    template = prompts_config.get('output_format', {}).get('template', {})
    keys = list(template.keys())
    prompt_parts.append(f"{{{', '.join(keys)}}}")

    # 业务规则
    business_rules = prompts_config.get('business_rules', {})
    if business_rules:
        prompt_parts.append("\n业务规则:")
        for table, rule in business_rules.items():
            prompt_parts.append(f"- {table}: {rule}")

    # 字段映射
    field_mappings = prompts_config.get('field_mappings', {})
    if field_mappings:
        prompt_parts.append("\n字段映射:")
        for key, value in field_mappings.items():
            prompt_parts.append(f"- {key}: {value}")

    # 表结构
    prompt_parts.append("\n表结构:")
    schema = schema_manager.config_loader.get_database_schema()
    for table in schema.get('tables', []):
        cols = [c['name'] for c in table.get('columns', [])]
        prompt_parts.append(f"{table['name']}: {','.join(cols)}")

    # 用户上下文
    if user_context:
        prompt_parts.append(f"\n用户上下文: {json.dumps(user_context, ensure_ascii=False)}")

    # 用户查询
    prompt_parts.append(f"\n查询: {query}")

    return "\n".join(prompt_parts)


def _parse_ai_response(ai_response: str) -> Dict[str, Any]:
    """解析AI响应"""
    import re

    try:
        # 尝试提取所有可能的JSON片段
        # 首先使用正则表达式匹配完整的JSON对象
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        json_matches = re.findall(json_pattern, ai_response, re.DOTALL)

        # 如果没有匹配到完整的JSON对象，尝试提取所有以{开始的片段
        if not json_matches:
            # 提取所有以{开始的位置
            start_positions = [m.start() for m in re.finditer(r'\{', ai_response)]

            for start_pos in start_positions:
                # 从{开始，截取到下一个{或字符串结束
                next_start = ai_response.find('{', start_pos + 1)
                if next_start == -1:
                    next_start = len(ai_response)

                # 提取片段
                json_str = ai_response[start_pos:next_start]

                # 尝试修复不完整的JSON
                # 1. 修复缺少的引号
                if json_str.count('"') % 2 != 0:
                    json_str += '"'

                # 2. 修复缺少的大括号
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                if open_braces > close_braces:
                    json_str += '}' * (open_braces - close_braces)

                # 3. 移除最后的逗号（如果有）
                json_str = json_str.rstrip().rstrip(',')

                # 4. 再次检查并添加缺少的大括号
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                if open_braces > close_braces:
                    json_str += '}' * (open_braces - close_braces)

                # 尝试解析修复后的JSON
                try:
                    json.loads(json_str)
                    json_matches.append(json_str)
                except json.JSONDecodeError:
                    # 尝试更激进的修复：只保留sql字段
                    sql_match = re.search(r'"sql"\s*:\s*"([^"]*)', json_str)
                    if sql_match:
                        sql = sql_match.group(1)
                        # 创建一个简单的JSON对象
                        simple_json = f'{"sql": "{sql}"}'
                        try:
                            json.loads(simple_json)
                            json_matches.append(simple_json)
                        except json.JSONDecodeError:
                            continue
                    continue

        # 如果仍然没有匹配到，尝试简单的find方法作为备选
        if not json_matches:
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_matches = [ai_response[json_start:json_end]]
            else:
                # 最后尝试：直接从响应中提取SQL语句
                sql_match = re.search(r'SELECT.*?FROM.*?(?:WHERE.*?)?(?:LIMIT.*?)?;', ai_response, re.DOTALL)
                if sql_match:
                    sql = sql_match.group(0)
                    # 创建一个简单的JSON对象
                    simple_json = f'{"sql": "{sql}"}'
                    json_matches = [simple_json]
                else:
                    raise ValueError("No valid JSON found in AI response")

        # 解析所有找到的JSON对象，选择最完整的那个
        best_result = None
        best_score = -1

        for json_str in json_matches:
            try:
                result = json.loads(json_str)

                # 检查是否有嵌套的template字段（Ollama可能返回这种格式）
                if "template" in result and isinstance(result["template"], dict):
                    result = result["template"]

                # 计算完整性评分（包含的关键字段越多，分数越高）
                required_fields = ["sql", "sql_type", "affected_tables", "estimated_rows", "risk_level", "explanation",
                                   "require_confirmation"]
                score = sum(1 for field in required_fields if field in result and result[field] is not None)

                # 如果有sql字段且不为空，给予额外加分
                if result.get("sql"):
                    score += 10
                # 如果sql字段存在但为None或空字符串，给予少量加分（比完全没有好）
                elif "sql" in result:
                    score += 1

                logger.info(f"找到JSON对象，完整性评分: {score}, 内容预览: {json_str[:100]}")

                if score > best_score:
                    best_score = score
                    best_result = result
            except json.JSONDecodeError:
                # 跳过无效的JSON
                continue

        if best_result is None:
            # 最后尝试：直接从响应中提取SQL语句
            sql_match = re.search(r'SELECT.*?FROM.*?(?:WHERE.*?)?(?:LIMIT.*?)?;', ai_response, re.DOTALL)
            if sql_match:
                sql = sql_match.group(0)
                best_result = {"sql": sql}
            else:
                raise ValueError("No valid JSON found in AI response")

        # 检查是否有有效的SQL
        if not best_result.get("sql"):
            logger.warning(f"AI响应未生成有效的SQL语句，选择的JSON对象评分: {best_score}")
            logger.warning(f"选中的JSON内容: {json.dumps(best_result, ensure_ascii=False)}")

            # 返回错误响应
            return {"sql": "", "sql_type": "UNKNOWN", "affected_tables": [], "estimated_rows": -1, "risk_level": "high",
                "explanation": "AI未能生成有效的SQL语句，请重新尝试或优化查询描述", "require_confirmation": True,
                "warnings": ["AI响应缺少SQL字段"]}

        # 确保必需字段存在并转换数据类型
        required_fields = ["sql", "sql_type", "affected_tables", "estimated_rows", "risk_level", "explanation",
                           "require_confirmation"]
        for field in required_fields:
            if field not in best_result:
                best_result[field] = None

        # 类型转换：确保estimated_rows是整数类型
        if isinstance(best_result.get("estimated_rows"), str):
            try:
                best_result["estimated_rows"] = int(best_result["estimated_rows"])
            except (ValueError, TypeError):
                best_result["estimated_rows"] = -1

        # 类型转换：确保require_confirmation是布尔类型
        if isinstance(best_result.get("require_confirmation"), str):
            best_result["require_confirmation"] = best_result["require_confirmation"].lower() in ['true', '1', 'yes']

        return best_result

    except Exception as e:
        logger.error(f"Failed to parse AI response: {e}")
        logger.error(f"原始响应内容: {ai_response[:500]}")

        # 最后尝试：直接从响应中提取SQL语句
        try:
            # 尝试从响应中提取所有可能的SQL语句
            # 1. 首先尝试匹配完整的SQL语句（带有分号）
            full_sql_pattern = r'SELECT\s+.+?\s+FROM\s+.+?(?:\s+WHERE\s+.+?)?(?:\s+LIMIT\s+\d+)?;'
            full_sql_matches = re.findall(full_sql_pattern, ai_response, re.DOTALL | re.IGNORECASE)

            # 2. 尝试匹配不完整的SQL语句（没有分号）
            partial_sql_pattern = r'SELECT\s+.+?\s+FROM\s+.+?(?:\s+WHERE\s+.+?)?(?:\s+LIMIT\s+\d+)?'
            partial_sql_matches = re.findall(partial_sql_pattern, ai_response, re.DOTALL | re.IGNORECASE)

            # 3. 合并所有匹配的SQL语句
            all_sql_matches = full_sql_matches + partial_sql_matches

            if all_sql_matches:
                # 清理并过滤SQL语句
                valid_sqls = []
                for sql in all_sql_matches:
                    # 清理SQL语句
                    sql = sql.strip()
                    # 确保SQL语句以分号结尾
                    if not sql.endswith(';'):
                        sql += ';'
                    # 移除可能的额外内容
                    if '```' in sql:
                        sql = sql.split('```')[0].strip()
                    if 'json' in sql.lower():
                        sql = sql.split('json')[0].strip()
                    # 检查是否包含FROM关键字
                    if 'FROM' in sql.upper():
                        valid_sqls.append(sql)

                if valid_sqls:
                    # 选择最长的SQL语句（通常是最完整的）
                    sql = max(valid_sqls, key=len)
                    return {"sql": sql, "sql_type": "SELECT", "affected_tables": [], "estimated_rows": -1,
                        "risk_level": "low", "explanation": "从AI响应中提取SQL语句", "require_confirmation": False,
                        "warnings": ["AI响应格式异常，已尝试提取SQL语句"]}

            # 4. 尝试从JSON片段中提取sql字段
            # 匹配所有可能的sql字段值
            sql_field_pattern = r'"sql"\s*:\s*"([^"]*)'
            sql_field_matches = re.findall(sql_field_pattern, ai_response, re.DOTALL | re.IGNORECASE)

            if sql_field_matches:
                # 清理并过滤SQL语句
                valid_sqls = []
                for sql in sql_field_matches:
                    # 清理SQL语句
                    sql = sql.strip()
                    # 移除可能的结尾内容
                    if '\n' in sql:
                        sql = sql.split('\n')[0].strip()
                    # 确保SQL语句以分号结尾
                    if not sql.endswith(';'):
                        sql += ';'
                    # 检查是否包含SELECT和FROM关键字
                    if 'SELECT' in sql.upper() and 'FROM' in sql.upper():
                        valid_sqls.append(sql)

                if valid_sqls:
                    # 选择最长的SQL语句（通常是最完整的）
                    sql = max(valid_sqls, key=len)
                    return {"sql": sql, "sql_type": "SELECT", "affected_tables": [], "estimated_rows": -1,
                        "risk_level": "low", "explanation": "从AI响应中提取SQL语句", "require_confirmation": False,
                        "warnings": ["AI响应格式异常，已尝试提取SQL语句"]}
        except:
            pass

        return {"sql": "", "sql_type": "UNKNOWN", "affected_tables": [], "estimated_rows": -1, "risk_level": "high",
            "explanation": f"解析AI响应失败: {str(e)}", "require_confirmation": True, "warnings": ["AI响应解析失败"]}


def _validate_sql(sql: str) -> Dict[str, Any]:
    """验证SQL语句"""
    dangerous_keywords = {"DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE", "SHOW", "DESCRIBE"}
    allowed_sql_types = {"SELECT", "UPDATE", "INSERT", "DELETE"}

    result = {"is_valid": True, "errors": [], "warnings": [], "sql_type": None}

    # 处理空SQL或None的情况
    if not sql or not isinstance(sql, str):
        result["is_valid"] = False
        result["errors"].append("SQL语句为空或无效")
        return result

    sql_upper = sql.upper().strip()

    # 检查危险关键词（使用单词边界匹配，避免误判字段名）
    import re
    for keyword in dangerous_keywords:
        if re.search(r'\b' + keyword + r'\b', sql_upper):
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

    # SQL注入检查：检测真正的注入模式
    import re

    # 检查分号后紧跟关键字的模式（真正的SQL注入）
    if re.search(r';\s*(DROP|ALTER|DELETE|UPDATE|INSERT|CREATE|TRUNCATE)', sql_upper, re.IGNORECASE):
        result["is_valid"] = False
        result["errors"].append("检测到SQL注入攻击：分号后紧跟危险关键字")
        return result

    # 检查注释后跟关键字的模式
    if re.search(r'--.*?(DROP|ALTER|DELETE|UPDATE|INSERT)', sql_upper, re.IGNORECASE):
        result["is_valid"] = False
        result["errors"].append("检测到SQL注入攻击：注释后跟危险关键字")
        return result

    # 检查UNION注入
    if re.search(r'UNION\s+SELECT', sql_upper, re.IGNORECASE):
        result["is_valid"] = False
        result["errors"].append("检测到SQL注入攻击：UNION注入")
        return result

    # 检查OR注入模式
    if re.search(r'\bOR\s+\d+\s*=\s*\d+', sql_upper, re.IGNORECASE):
        result["is_valid"] = False
        result["errors"].append("检测到SQL注入攻击：OR注入")
        return result

    # 检查AND注入模式
    if re.search(r'\bAND\s+\d+\s*=\s*\d+', sql_upper, re.IGNORECASE):
        result["is_valid"] = False
        result["errors"].append("检测到SQL注入攻击：AND注入")
        return result

    return result


def _evaluate_risk(response_data: Dict[str, Any]) -> str:
    """评估风险等级"""
    sql = response_data.get("sql", "")
    sql_type = response_data.get("sql_type", "")
    estimated_rows = response_data.get("estimated_rows")

    # 确保 estimated_rows 是整数类型，None 则设为 -1
    if estimated_rows is None:
        estimated_rows = -1
    elif not isinstance(estimated_rows, int):
        try:
            estimated_rows = int(estimated_rows)
        except (ValueError, TypeError):
            estimated_rows = -1

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

    # 如果sql为None或空字符串，直接返回空建议
    if not sql or not isinstance(sql, str):
        return suggestions

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
    logger.info("=" * 60)
    logger.info("Starting db-ai-server MCP Server...")
    logger.info("=" * 60)

    # 初始化服务器
    mcp_server = initialize_server()

    # 测试AI推理引擎连接
    try:
        # 先初始化 session（建立 TCP 连接池）
        await ai_client._get_session()
        logger.info("AI client session initialized")

        await ai_client.test_connection()
        engine_config = get_config_loader().get_inference_config()
        logger.info(f"✓ AI inference engine ({engine_config.get('type')}) connection successful")

        # 预热模型：发送一个轻量级请求让LM Studio加载模型
        logger.info("Warming up AI model...")
        try:
            warmup_result = await ai_client.generate(prompt="Say 'ready' in one word.", temperature=0.1, num_predict=10)
            logger.info(f"✓ AI model warmup successful: {warmup_result[:50]}")
        except Exception as warmup_err:
            logger.warning(f"Model warmup failed (non-critical): {warmup_err}")
    except Exception as e:
        engine_config = get_config_loader().get_inference_config()
        logger.error(f"✗ Failed to connect to {engine_config.get('type')}: {e}")
        logger.info(f"Please ensure {engine_config.get('type')} is running")
        return

    # 启动服务器
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
