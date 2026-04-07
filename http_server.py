#!/usr/bin/env python3
"""
db-ai-server HTTP Server
为C#客户端提供HTTP接口调用MCP服务器
"""

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("错误: 未安装fastapi和uvicorn，请运行: pip install fastapi uvicorn pydantic")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # 输出到stderr，避免干扰HTTP响应
)
logger = logging.getLogger(__name__)

app = FastAPI(title="DB-AI-Server HTTP API")

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExecuteSqlRequest(BaseModel):
    """执行SQL请求模型"""
    sql: str


class GenerateSqlRequest(BaseModel):
    """生成SQL请求模型"""
    query: str

# MCP服务器进程
mcp_process = None


class MCPClient:
    """简单的MCP客户端，通过stdio与MCP服务器通信"""

    def __init__(self):
        self.process = None
        self.initialized = False
        self.request_id = 0

    async def start(self):
        """启动MCP服务器进程并初始化"""
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            "src/mcp_server.py",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=Path(__file__).parent
        )
        logger.info("MCP服务器进程已启动")

        # 等待进程启动
        await asyncio.sleep(0.5)

        # 发送初始化请求
        await self._initialize()

    async def _initialize(self):
        """发送MCP初始化请求"""
        init_request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "db-ai-server-http",
                    "version": "1.0.0"
                }
            }
        }

        await self._send_request(init_request)
        response = await self._read_response()

        if "error" in response:
            logger.error(f"MCP初始化失败: {response['error']}")
            raise HTTPException(status_code=500, detail="MCP初始化失败")

        # 发送initialized通知
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        await self._send_request(initialized_notification)

        self.initialized = True
        logger.info("MCP客户端初始化完成")

    def _clean_json_string(self, text: str) -> str:
        """清理JSON字符串，移除可能的BOM或其他非JSON字符"""
        if not text:
            return text

        # 移除BOM
        text = text.lstrip('\ufeff')

        # 查找第一个 { 或 [
        start_idx = -1
        for i, char in enumerate(text):
            if char in '{[':
                start_idx = i
                break

        if start_idx > 0:
            logger.warning(f"在JSON字符串开头发现 {start_idx} 个非JSON字符: {text[:start_idx]}")
            text = text[start_idx:]

        return text

    async def _send_request(self, request: dict):
        """发送请求到MCP服务器"""
        request_json = json.dumps(request, ensure_ascii=False) + "\n"
        self.process.stdin.write(request_json.encode('utf-8'))
        await self.process.stdin.drain()

    async def _read_response(self) -> dict:
        """读取MCP服务器响应"""
        response_line = await self.process.stdout.readline()

        if not response_line:
            raise HTTPException(status_code=500, detail="MCP服务器无响应")

        response_str = response_line.decode('utf-8', errors='ignore').strip()

        try:
            response = json.loads(response_str)
            return response
        except json.JSONDecodeError as e:
            logger.error(f"解析MCP响应失败: {e}, 响应内容: {response_str[:200]}")
            raise HTTPException(status_code=500, detail=f"解析响应失败: {e}")

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用MCP工具"""
        if not self.process or self.process.returncode is not None:
            await self.start()

        if not self.initialized:
            await asyncio.sleep(0.5)  # 等待初始化完成

        # 构造MCP请求
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

        await self._send_request(request)
        response = await self._read_response()

        if "error" in response:
            logger.error(f"MCP工具调用失败: {response['error']}")
            raise HTTPException(status_code=500, detail=str(response["error"]))

        result = response.get("result", {})

        # 提取content数组中的text
        if "content" in result and len(result["content"]) > 0:
            content_item = result["content"][0]

            # 如果content_item是字典，获取text字段
            if isinstance(content_item, dict):
                if "text" in content_item:
                    text = content_item["text"]
                    logger.info(f"提取到text字段，长度: {len(text)}, 前100字符: {text[:100]}")
                    # 清理JSON字符串
                    text = self._clean_json_string(text)
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError as e:
                        logger.error(f"解析content text失败: {e}, 内容: {text[:200]}")
                        raise HTTPException(status_code=500, detail=f"解析content text失败: {e}")
            # 如果content_item有text属性
            elif hasattr(content_item, 'text'):
                text = content_item.text
                logger.info(f"提取到text属性，长度: {len(text)}, 前100字符: {text[:100]}")
                # 清理JSON字符串
                text = self._clean_json_string(text)
                try:
                    return json.loads(text)
                except json.JSONDecodeError as e:
                    logger.error(f"解析content.text失败: {e}, 内容: {text[:200]}")
                    raise HTTPException(status_code=500, detail=f"解析content.text失败: {e}")

        # 如果没有content或无法提取text，返回原始result
        return result


mcp_client = MCPClient()


@app.on_event("startup")
async def startup_event():
    """启动时初始化MCP客户端"""
    await mcp_client.start()


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
    if mcp_client.process:
        mcp_client.process.terminate()
        await mcp_client.process.wait()


@app.post("/mcp/execute_sql")
async def execute_sql(request: ExecuteSqlRequest):
    """
    执行SQL查询

    请求格式:
    {
        "sql": "SELECT * FROM users WHERE status='active'"
    }
    """
    try:
        sql = request.sql
        if not sql:
            raise HTTPException(status_code=400, detail="缺少sql参数")

        result = await mcp_client.call_tool("execute_sql", {"sql": sql})
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行SQL失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp/generate_sql")
async def generate_sql(request: GenerateSqlRequest):
    """
    根据自然语言生成SQL

    请求格式:
    {
        "query": "查询所有激活的用户"
    }
    """
    try:
        query = request.query
        if not query:
            raise HTTPException(status_code=400, detail="缺少query参数")

        result = await mcp_client.call_tool("generate_sql", {"query": query})
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成SQL失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "db-ai-server-http"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
