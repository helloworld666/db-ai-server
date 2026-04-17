# DB-AI-Server v7.0

**数据库AI服务器** - 基于LangChain v1.0的AI驱动SQL生成系统

> **v7.0重大更新**: 全面遵循LangChain v1.0规范，采用ReAct Agent实现工具链调用。

## 核心特性

- ✅ **LangChain v1.0**: 使用 `@tool` 装饰器和 Runnable 接口
- ✅ **零硬编码**: 所有提示词、业务逻辑从配置文件加载
- ✅ **LLM自主决策**: 工具调用顺序由LLM决定
- ✅ **完整SQL支持**: SELECT/UPDATE/INSERT/DELETE
- ✅ **多引擎支持**: OpenAI/DeepSeek/通义千问/Ollama/LM Studio
- ✅ **安全验证**: SQL注入检测、风险评估

---

## 快速开始

### 1. 安装依赖

```bash
cd e:/develop/db-ai-server
pip install -r requirements.txt
```

### 2. 配置推理引擎

编辑 `config/server_config.json`：

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

### 通用处理流程

所有操作都遵循相同的基础流程：

```
用户输入 → MCP Server → ReAct Agent → 工具调用循环 → 返回结果
```

```python
# 1. 构建消息
messages = [
    SystemMessage(content=system_prompt),  # 从 config/prompts.json 加载
    HumanMessage(content=query)
]

# 2. LLM 推理并决定工具调用
llm_with_tools = llm.bind_tools(tools)
response = await llm_with_tools.ainvoke(messages)

# 3. 执行工具调用循环
while response.tool_calls:
    for tool_call in response.tool_calls:
        result = await tools_dict[tool_call.name].ainvoke(tool_call.args)
        messages.append(ToolMessage(content=str(result), tool_call_id=tool_call.id))
    response = await llm_with_tools.ainvoke(messages)

# 4. 返回最终结果
return response.content
```

### SELECT 查询操作

**用户输入:** "查询所有用户"

**工具链:** `get_database_schema → execute_sql(SELECT)`

```
迭代 1: LLM 调用 get_database_schema() 获取表结构
         ↓
迭代 2: LLM 调用 execute_sql("SELECT * FROM users")
         ↓
最终结果: {"success": true, "sql_list": ["SELECT * FROM users"]}
```

### INSERT 插入操作

**用户输入:** "添加新用户张三，年龄25岁"

**工具链:** `get_database_schema → execute_sql(INSERT)`

**插入并返回:**
```
用户输入: "添加新用户李四，年龄30岁，并返回添加的数据"
工具链: get_database_schema → execute_sql(INSERT) → execute_sql(SELECT) → 返回结果
```

### UPDATE 更新操作

**用户输入:** "将ID为1的用户年龄改为30"

**工具链:** `get_database_schema → execute_sql(UPDATE)`

**更新并返回:**
```
用户输入: "将ID为1的用户年龄改为30，并返回更新后的数据"
工具链: get_database_schema → execute_sql(UPDATE) → execute_sql(SELECT) → 返回结果
```

### DELETE 删除操作

**用户输入:** "删除ID为5的用户"

**工具链:** `get_database_schema → execute_sql(DELETE)`

**注意:** 无 WHERE 条件的 DELETE 会被拦截验证。

### 操作响应格式

| SQL 类型 | 操作描述 | 返回内容 |
|----------|----------|----------|
| SELECT | 查询数据 | `{"success": true, "data": [...]}` |
| INSERT | 插入数据 | `{"success": true, "affected_rows": N}` |
| UPDATE | 更新数据 | `{"success": true, "affected_rows": N}` |
| DELETE | 删除数据 | `{"success": true, "affected_rows": N}` |

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

### 返回数据规则

如果用户要求"返回结果"，UPDATE/INSERT 操作后 Agent 会自动追加 SELECT 查询。

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        MCP Server                           │
│                      (mcp_server.py)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      ReAct Agent                           │
│                 (src/agents/react_agent.py)                 │
│  - 维护工具集合 │ 管理对话上下文 │ 执行工具调用循环          │
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
| `config/settings.yaml` | 服务配置 |
| `config/schema/*.json` | 数据库 Schema 定义 |

---

## MCP 工具

| 工具名 | 功能 |
|--------|------|
| `get_database_schema` | 获取数据库表结构 |
| `generate_sql` | 根据自然语言生成SQL |
| `execute_sql` | 执行 SQL 语句 |
| `validate_sql` | 验证 SQL 安全性 |
| `get_server_status` | 获取服务器状态 |

---

## HTTP API

### 生成SQL

```http
POST /mcp/generate_sql
Content-Type: application/json

{"query": "查询所有用户"}
```

**响应:**
```json
{
  "success": true,
  "sql_list": ["SELECT * FROM users"]
}
```

### 执行SQL

```http
POST /mcp/execute_sql
Content-Type: application/json

{"sql": "SELECT * FROM users"}
```

---

## 错误处理

| 错误类型 | 响应 |
|----------|------|
| 表不存在 | `{"success": false, "error": "表 'xxx' 不存在"}` |
| SQL验证失败 | `{"success": false, "error": "SQL验证失败", "validation": {...}}` |
| 迭代超限 | `{"success": false, "error": "达到最大迭代次数限制"}` |

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
│   └── schema/                 # 数据库Schema配置
└── src/                        # 源代码
    ├── agents/react_agent.py   # ReAct Agent
    ├── tools/registry.py       # 工具注册表
    ├── schema/manager.py       # Schema管理器
    ├── security/validator.py   # SQL验证器
    └── prompts/manager.py      # 提示词管理器
```

---

## Python客户端

```python
import asyncio
import json
from mcp import ClientSession, StdioServerParameters

async def generate_sql(query: str):
    async with ClientSession() as session:
        await session.connect(StdioServerParameters(
            command="python",
            args=["mcp_server.py"]
        ))

        result = await session.call_tool(
            "generate_sql",
            {"query": query}
        )

        return json.loads(result.content[0].text)

# 使用
sql = await generate_sql("查询所有用户")
print(sql)
```

---

## C#客户端

```csharp
// 注册服务
services.AddHttpClient<DbAiService>();

// 使用
var result = await dbAiService.GenerateAndExecuteAsync("查询所有用户");
if (result.Success)
{
    foreach (var row in result.Rows)
    {
        Console.WriteLine($"用户名: {row["name"]}");
    }
}
```

---

## 故障排除

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| Failed to connect | 推理引擎未启动 | 检查 LM Studio/Ollama 是否运行 |
| No valid JSON | 模型响应无效 | 降低 temperature 到 0.1 |
| Model not found | 模型未加载 | 加载对应模型 |
| 响应很慢 | 模型太大 | 使用更小的模型 |

---

## 代码规范

```bash
# Windows 格式化
.\format.bat

# 检查
.\lint.bat
```

---

**Made with ❤️ for db-ai-server MCP integration**
