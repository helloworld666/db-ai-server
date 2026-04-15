"""HTTP API服务器 - FastAPI"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core.config.settings import get_settings, Settings
from ..llm.factory import LLMFactory
from ..database.connection import DatabaseConnection
from ..database.schema import SchemaManager
from ..database.prompts import PromptManager
from ..security.validator import SQLValidator
from ..agents.sql_agent import SQLAgent
from ..tools.db_tools import create_database_tools

logger = logging.getLogger(__name__)

# 全局应用实例
app: Optional[FastAPI] = None
db_agent: Optional[SQLAgent] = None


class QueryRequest(BaseModel):
    """查询请求"""
    query: str
    user_context: Optional[Dict[str, Any]] = None


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    global app, db_agent

    # 加载设置
    settings = get_settings()

    # 初始化组件
    config_path = str(settings.config_dir)
    db_config = settings.database.connection_string

    # 创建数据库连接
    db_connection = None
    if db_config:
        try:
            db_connection = DatabaseConnection(db_config)
            db_connection.test_connection()
        except Exception as e:
            logger.warning(f"数据库连接失败: {e}")

    # 创建管理器
    schema_manager = SchemaManager(config_path)
    prompt_manager = PromptManager(config_path)
    sql_validator = SQLValidator(config_path)

    # 创建LLM
    llm_config = {
        "provider": settings.llm.provider,
        "model": settings.llm.model,
        "api_key": settings.llm.api_key,
        "base_url": settings.llm.base_url,
        "temperature": settings.llm.temperature,
        "max_tokens": settings.llm.max_tokens,
    }

    # 获取AI客户端
    ai_client = None
    try:
        from ..database.llm_client import get_ai_client
        ai_client = get_ai_client(settings)
    except ImportError:
        pass

    llm = LLMFactory.create(llm_config, existing_client=ai_client)

    # 创建工具
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

    # 创建FastAPI应用
    app = FastAPI(
        title="DB-AI-Server API",
        description="AI-powered database SQL generation API",
        version="2.0.0"
    )

    # 添加路由
    @app.get("/health")
    async def health_check():
        """健康检查"""
        return {
            "status": "ok",
            "version": "2.0.0"
        }

    @app.get("/schema")
    async def get_schema():
        """获取数据库Schema"""
        schema = schema_manager.get_full_schema()
        return schema

    @app.post("/query")
    async def query(request: QueryRequest):
        """执行查询"""
        if not db_agent:
            raise HTTPException(status_code=500, detail="Agent未初始化")

        result = await db_agent.ainvoke(
            query=request.query,
            user_context=request.user_context
        )
        return result

    @app.get("/status")
    async def get_status():
        """获取服务器状态"""
        if not db_agent:
            raise HTTPException(status_code=500, detail="Agent未初始化")

        return {
            "server": {
                "name": "db-ai-server",
                "version": "2.0.0"
            },
            "agent": db_agent.get_status(),
            "database": {
                "connected": db_connection is not None,
                "tables_count": len(schema_manager.get_all_table_names())
            }
        }

    @app.post("/validate")
    async def validate_sql(sql: str):
        """验证SQL"""
        result = sql_validator.validate(sql)
        return result

    return app


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """运行HTTP服务器"""
    import uvicorn

    if app is None:
        create_app()

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
