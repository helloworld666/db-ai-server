#!/usr/bin/env python3
"""
db-ai-server HTTP Server v5.0
为C#客户端提供HTTP接口调用MCP服务器

核心原则：
1. 所有配置从JSON文件读取，禁止硬编码
2. 工具调用完全由LLM自主决定
3. 使用LangChain标准API
"""

import asyncio
import json
import logging
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


class InvokeToolRequest(BaseModel):
    """通用工具调用请求"""
    tool: str = Field(..., description="要调用的工具名")
    arguments: Dict[str, Any] = Field(default={}, description="工具参数")


class QueryRequest(BaseModel):
    """自然语言查询请求"""
    query: str = Field(..., description="自然语言查询")
    context: Optional[Dict[str, Any]] = Field(default=None, description="可选上下文")


class ExecuteSqlRequest(BaseModel):
    """执行SQL请求模型"""
    sql: str = Field(..., description="要执行的SQL语句")


class GenerateSqlRequest(BaseModel):
    """生成SQL请求模型"""
    query: str = Field(..., description="自然语言查询描述")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ lifespan 事件处理器 """
    await mcp_client.start()
    yield
    # 关闭时清理资源
    if mcp_client.process:
        mcp_client.process.terminate()
        await mcp_client.process.wait()
    if mcp_client.stderr_task:
        mcp_client.stderr_task.cancel()
        try:
            await mcp_client.stderr_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="DB-AI-Server HTTP API", version="5.0.0", lifespan=lifespan)

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MCPClient:
    """简单的MCP客户端，通过stdio与MCP服务器通信"""

    def __init__(self):
        self.process = None
        self.initialized = False
        self.request_id = 0
        self.stderr_task = None
        self._lock = asyncio.Lock()

    async def start(self):
        """启动MCP服务器进程并初始化"""
        project_root = Path(__file__).parent
        python_exe = sys.executable
        logger.info(f"使用Python: {python_exe}")

        self.process = await asyncio.create_subprocess_exec(
            python_exe,
            "mcp_server.py",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(project_root)
        )

        # 启动stderr读取任务
        self.stderr_task = asyncio.create_task(self._read_stderr())

        # 等待MCP服务器就绪
        await asyncio.sleep(2)

        # 发送initialize请求
        await self._send_initialize()

        self.initialized = True
        logger.info("MCP客户端初始化完成")

    async def _send_initialize(self):
        """发送MCP initialize请求"""
        init_request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "http-client", "version": "5.0.0"}
            }
        }
        logger.info("发送initialize请求...")
        await self._send_request(init_request)
        response = await self._read_response()
        logger.info(f"initialize响应: {response}")

        # 发送initialized通知
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        await self._send_request(initialized_notification)
        logger.info("发送initialized通知完成")

    async def _read_stderr(self):
        """读取MCP服务器的stderr输出"""
        try:
            while self.process and self.process.returncode is None:
                line = await self.process.stderr.readline()
                if not line:
                    break
                line_str = line.decode('utf-8', errors='ignore').strip()
                if line_str:
                    logger.info(f"[MCP服务器] {line_str}")
        except Exception as e:
            logger.error(f"读取stderr失败: {e}")

    async def _send_request(self, request: dict):
        """发送请求到MCP服务器"""
        request_json = json.dumps(request) + "\n"
        logger.info(f"发送请求: {request_json[:200]}")
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()

    async def _read_response(self) -> dict:
        """读取MCP服务器响应"""
        try:
            while True:
                line = await asyncio.wait_for(
                    self.process.stdout.readline(),
                    timeout=120.0
                )
                if not line:
                    logger.error("MCP服务器已关闭")
                    raise HTTPException(status_code=500, detail="MCP服务器已关闭")

                line_str = line.decode('utf-8', errors='ignore').strip()

                # 跳过空行
                if not line_str:
                    continue

                # 跳过非JSON行（日志输出）
                if not line_str.startswith('{'):
                    logger.debug(f"跳过非JSON行: {line_str[:100]}")
                    continue

                logger.info(f"收到响应: {line_str[:200]}")
                return json.loads(line_str)
        except asyncio.TimeoutError:
            logger.error("读取响应超时")
            raise HTTPException(status_code=504, detail="MCP服务器响应超时")
        except json.JSONDecodeError as e:
            logger.error(f"解析响应失败: {e}")
            raise HTTPException(status_code=500, detail=f"解析MCP响应失败: {e}")

    def _clean_json_string(self, text: str) -> str:
        """清理JSON字符串"""
        text = text.strip()
        if text.startswith('```json'):
            text = text[7:]
        elif text.startswith('```'):
            text = text[3:]
        if text.endswith('```'):
            text = text[:-3]
        return text.strip()

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用MCP工具（使用锁保护并发访问）"""
        async with self._lock:
            if not self.process or self.process.returncode is not None:
                await self.start()

            if not self.initialized:
                retry_count = 0
                while not self.initialized and retry_count < 10:
                    await asyncio.sleep(0.1)
                    retry_count += 1

            self.request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            logger.info(f"调用工具: {tool_name}, 参数: {arguments}")
            await self._send_request(request)
            response = await self._read_response()

        if "error" in response:
            logger.error(f"MCP工具调用失败: {response['error']}")
            raise HTTPException(status_code=500, detail=str(response["error"]))

        result = response.get("result", {})

        # 提取content数组中的text
        if "content" in result and len(result["content"]) > 0:
            content_item = result["content"][0]
            if isinstance(content_item, dict) and "text" in content_item:
                text = content_item["text"]
                text = self._clean_json_string(text)
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"result": text}
            elif hasattr(content_item, 'text'):
                text = content_item.text
                text = self._clean_json_string(text)
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"result": text}

        return result


# MCP客户端实例
mcp_client = MCPClient()


@app.post("/mcp/invoke")
async def invoke_tool(request: InvokeToolRequest):
    """
    通用工具调用端点 - 由调用方指定工具名和参数

    请求格式:
    {
        "tool": "execute_sql",
        "arguments": {"sql": "SELECT * FROM users"}
    }
    """
    try:
        if not request.tool:
            raise HTTPException(status_code=400, detail="缺少tool参数")

        result = await mcp_client.call_tool(request.tool, request.arguments)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"工具调用失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp/query")
async def query(request: QueryRequest):
    """
    自然语言查询 - 由Agent自主决定调用什么工具

    请求格式:
    {
        "query": "查询所有用户",
        "context": {"userId": 123}
    }
    """
    try:
        if not request.query:
            raise HTTPException(status_code=400, detail="缺少query参数")

        arguments = {"query": request.query}
        if request.context:
            arguments["context"] = request.context

        # 调用smart_execute工具，由Agent内部自主决定工具调用链
        result = await mcp_client.call_tool("smart_execute", arguments)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp/smart_execute")
async def smart_execute(request: QueryRequest):
    """
    智能执行 - LLM完全自主决定工具调用链

    请求格式:
    {
        "query": "查询所有启用的货架"
    }
    """
    try:
        if not request.query:
            raise HTTPException(status_code=400, detail="缺少query参数")

        logger.info(f"Smart Execute请求: {request.query}")
        result = await mcp_client.call_tool("smart_execute", {"query": request.query})
        logger.info(f"Smart Execute结果: {str(result)[:500]}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"智能执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp/execute_sql")
async def execute_sql(request: ExecuteSqlRequest):
    """执行SQL查询 - C#客户端兼容端点"""
    try:
        if not request.sql:
            raise HTTPException(status_code=400, detail="缺少sql参数")
        result = await mcp_client.call_tool("execute_sql", {"sql": request.sql})
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行SQL失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp/generate_sql")
async def generate_sql(request: GenerateSqlRequest):
    """根据自然语言生成SQL - C#客户端兼容端点"""
    try:
        if not request.query:
            raise HTTPException(status_code=400, detail="缺少query参数")
        logger.info(f"生成SQL请求: {request.query}")
        result = await mcp_client.call_tool("generate_sql", {"query": request.query})
        logger.info(f"生成SQL结果: {result}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成SQL失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mcp/get_schema")
async def get_schema():
    """获取数据库结构 - C#客户端兼容端点"""
    try:
        result = await mcp_client.call_tool("get_database_schema", {})
        return result
    except Exception as e:
        logger.error(f"获取数据库结构失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "db-ai-server-http", "version": "5.0.0"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
