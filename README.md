# DB-AI-Server v7.0

**数据库AI服务器** - 基于LangChain v1.0的AI驱动SQL生成系统

> **v7.0更新**: 全面遵循LangChain v1.0规范，采用ReAct Agent实现工具链调用。LLM完全自主决定工具调用顺序。
> - **推荐**: LM Studio + gemma-4-e4b-it 模型（工具调用能力强）
> - **零硬编码**: 敏感字段、表结构全部从Schema配置动态获取

## 核心特性

- ✅ **LangChain v1.0**: 使用 `@tool` 装饰器和 Runnable 接口
- ✅ **零硬编码**: 所有提示词、表结构、敏感字段从配置加载
- ✅ **LLM自主决策**: 工具调用顺序由LLM决定（smart_execute）
- ✅ **完整SQL支持**: SELECT/UPDATE/INSERT/DELETE
- ✅ **敏感字段处理**: LLM自主决定（INSERT时MD5加密，SELECT时排除敏感字段）
- ✅ **多引擎支持**: LM Studio/OpenAI/DeepSeek/通义千问
- ✅ **安全验证**: SQL注入检测、风险评估

---

## 快速开始

### 1. 安装依赖

```bash
cd e:/develop/db-ai-server
pip install -r requirements.txt
```

### 2. 配置推理引擎

**推荐: LM Studio + gemma 模型**（免费、本地、工具调用能力强）

1. 下载安装 [LM Studio](https://lmstudio.ai)
2. 下载 `gemma-4-e4b-it` 模型（INT4量化，8G显存可用）
3. 启动 LM Studio 本地服务器（默认端口 62666）

编辑 `config/server_config.json`：

```json
{
  "inference_engine": {
    "type": "lmstudio",
    "base_url": "http://127.0.0.1:62666/v1",
    "model": "gemma-4-e4b-it",
    "temperature": 0,
    "max_tokens": 2000
  }
}
```

**或使用云端API（如 DeepSeek）**:

```json
{
  "inference_engine": {
    "type": "deepseek",
    "api_key": "你的API Key",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-coder"
  }
}
```

### 3. 配置数据库

```json
{
  "database": {
    "connection_string": "mysql://root:password@localhost:3306/yourdb"
  }
}
```

### 4. 运行

```bash
# MCP服务器（stdio模式）
python mcp_server.py

# HTTP桥接服务器
python http_server.py
```

---

## 执行流程

### 智能执行流程（推荐）

**推荐使用 `smart_execute`**，LLM完全自主决定工具调用链：

```
用户查询 → /mcp/smart_execute → ReAct Agent → LLM自主决定工具 → 返回结果
```

#### smart_execute 完整流程

```
用户输入: "查询所有启用的货架"
         ↓
迭代 1: LLM 调用 get_database_schema() 获取表结构
         ↓
迭代 2: LLM 调用 generate_sql() 生成SQL
         ↓
迭代 3: LLM 调用 validate_sql() 验证安全性
         ↓
迭代 4: LLM 调用 execute_sql() 执行SQL
         ↓
最终结果: {"success": true, "columns": [...], "rows": [...], "affected_rows": N}
```

> **关键区别**: LLM自主决定调用顺序和次数，无需客户端两阶段调用。

---

### MCP 工具列表

| 工具名 | 功能 | 使用场景 |
|--------|------|----------|
| `smart_execute` | 智能执行，LLM自主决定工具链 | **推荐** - 自然语言查询 |
| `get_database_schema` | 获取数据库表结构 | 单独获取Schema |
| `generate_sql` | 根据自然语言生成SQL | 只需生成SQL |
| `execute_sql` | 执行SQL语句 | 已知SQL直接执行 |
| `validate_sql` | 验证SQL安全性 | SQL安全检查 |
| `get_server_status` | 获取服务器状态 | 服务健康检查 |

---

## HTTP API

### 智能执行（推荐）

```http
POST /mcp/smart_execute
Content-Type: application/json

{"query": "查询所有启用的货架"}
```

**响应:**
```json
{
  "success": true,
  "columns": ["货架ID", "货架名称", "是否启用"],
  "rows": [
    [1, "A区货架", "是"],
    [2, "B区货架", "否"]
  ]
}
```

### 自然语言查询（等同于smart_execute）

```http
POST /mcp/query
Content-Type: application/json

{"query": "查询所有用户"}
```

---

## C#客户端

### 使用 smart_execute（推荐）

```csharp
// 注册服务
services.AddHttpClient<DbAiService>();

// 使用 - 单一调用，LLM自主决定工具链
var result = await dbAiService.SmartExecuteAsync("查询所有启用的货架");
if (result.Success)
{
    foreach (var row in result.Rows)
    {
        Console.WriteLine($"货架: {row["货架名称"]}, 状态: {row["是否启用"]}");
    }
}
```

### 服务端响应格式

```json
{
  "success": true,
  "columns": ["列1", "列2", ...],
  "rows": [[值1, 值2, ...], ...],
  "affected_rows": N
}
```

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        HTTP Server                           │
│                      (http_server.py)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ /mcp/query  │  │/smart_execute│  │ /mcp/invoke        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        MCP Server                           │
│                      (mcp_server.py)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      ReAct Agent                           │
│                 (src/agents/react_agent.py)                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ LLM自主决定工具调用链:                                │   │
│  │ get_schema → generate_sql → validate_sql → execute  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Tool Registry                           │
│                  (src/tools/registry.py)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ get_schema  │  │ execute_sql │  │ validate_sql│       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   SchemaManager  │ │DatabaseConnection│ │  SQLValidator    │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

---

## 核心组件

| 模块 | 文件 | 职责 |
|------|------|------|
| HTTP Server | `http_server.py` | HTTP桥接，为客户端提供REST API |
| MCP Server | `mcp_server.py` | MCP 协议处理，工具注册 |
| ReAct Agent | `src/agents/react_agent.py` | LLM 工具调用循环 |
| Tool Registry | `src/tools/registry.py` | LangChain v1.0 工具定义 |
| Schema Manager | `src/schema/manager.py` | 数据库结构管理 |
| SQL Validator | `src/security/validator.py` | SQL 安全验证 |
| Prompt Manager | `src/prompts/manager.py` | 提示词管理 |
| LLM Factory | `src/llm/factory.py` | LLM 实例创建 |

---

## 配置文件

| 文件 | 用途 |
|------|------|
| `config/prompts.json` | 提示词和验证规则 |
| `config/server_config.json` | 服务配置 |
| `config/schema/*.json` | 数据库 Schema 定义 |

---

## 安全规则

### 禁止的危险操作

根据 `config/prompts.json` 配置，以下 SQL 关键字被禁止：

| 关键字 | 说明 |
|--------|------|
| DROP | 删除表/数据库 |
| TRUNCATE | 清空表 |
| ALTER | 修改表结构 |
| CREATE | 创建表/数据库 |
| GRANT | 授予权限 |
| REVOKE | 撤销权限 |

### DELETE 操作保护

```json
{
  "sql_validation": {
    "require_where_for_delete": true
  }
}
```

- **有 WHERE 条件**: 正常执行
- **无 WHERE 条件**: 验证失败

---

## Python客户端

```python
import asyncio
import json
from mcp import ClientSession, StdioServerParameters

async def smart_execute(query: str):
    async with ClientSession() as session:
        await session.connect(StdioServerParameters(
            command="python",
            args=["mcp_server.py"]
        ))

        result = await session.call_tool(
            "smart_execute",
            {"query": query}
        )

        return json.loads(result.content[0].text)

# 使用
result = await smart_execute("查询所有启用的货架")
print(result)
```

---

## 故障排除

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| Failed to connect | 推理引擎未启动 | 检查 LM Studio 是否运行 |
| No valid JSON | 模型响应无效 | 降低 temperature 到 0.1 |
| Model not found | 模型未加载 | 加载对应模型 |
| 响应很慢 | 模型太大 | 使用更小的模型 |
| 工具调用不正确 | 模型对指令遵循能力弱 | 换用 gemma-4-e4b-it（通用模型）而非代码专用模型 |
| SELECT查询包含敏感字段 | 模型未遵循规则 | 使用通用模型 + 优化提示词 |

---

## 代码规范

```bash
# Windows格式化
.\format.bat

# 检查
.\lint.bat
```

---

## 目录结构

```
db-ai-server/
├── README.md                    # 项目说明
├── requirements.txt             # Python依赖
├── mcp_server.py               # MCP服务器入口 (v7.0)
├── http_server.py              # HTTP桥接服务器
├── config/                      # 配置目录
│   ├── prompts.json            # 提示词模板
│   ├── server_config.json      # 服务配置
│   └── schema/                 # 数据库Schema配置
└── src/                        # 源代码
    ├── agents/react_agent.py   # ReAct Agent
    ├── tools/registry.py       # 工具注册表
    ├── schema/manager.py       # Schema管理器
    ├── security/validator.py   # SQL验证器
    ├── database/connection.py  # 数据库连接
    ├── llm/factory.py          # LLM工厂
    └── prompts/manager.py      # 提示词管理器
```

---

**Made with ❤️ for db-ai-server MCP integration**
