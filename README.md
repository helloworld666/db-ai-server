# DB-AI-Server

**数据库AI服务器** - 一个独立、可配置的MCP服务器，用于通过AI（Ollama）生成和管理数据库SQL语句。

## 🌟 特性

- ✅ **完整SQL支持**: 支持SELECT查询、UPDATE更新、INSERT插入、DELETE删除操作
- ✅ **智能查询优化**: 自动分析SQL并提供性能优化建议
- ✅ **自然语言接口**: 通过自然语言描述直接生成SQL，无需编写数据访问层
- ✅ **完全独立**: 不依赖任何特定项目，可被任何项目使用
- ✅ **配置驱动**: 数据库Schema、提示词、规则全部通过JSON/MD配置文件管理
- ✅ **本地LLM**: 基于Ollama本地推理，保护数据隐私
- ✅ **安全可控**: 多层SQL验证、风险评估、权限控制
- ✅ **MCP标准**: 完全遵循MCP协议标准
- ✅ **灵活扩展**: 支持自定义模型、自定义验证规则
- ✅ **字段注释支持**: 自动查询数据库字段注释，返回中文列头信息

## 📋 目录结构

```
db-ai-server/
├── README.md                          # 项目说明（本文件）
├── requirements.txt                   # Python依赖
├── setup.py                          # 安装脚本
├── http_server.py                    # HTTP桥接服务器
├── config/                           # 配置目录
│   ├── server_config.json           # 服务器配置
│   ├── database_schema.json         # 数据库Schema配置
│   ├── prompts.json                 # 提示词模板配置
│   └── security_rules.json          # 安全规则配置
├── src/                             # 源代码
│   ├── __init__.py
│   ├── mcp_server.py               # MCP服务器主程序
│   ├── ollama_client.py            # Ollama客户端
│   ├── config_loader.py            # 配置加载器
│   ├── schema_manager.py           # Schema管理器
│   ├── prompt_builder.py           # 提示词构建器
│   ├── response_validator.py       # 响应验证器
│   ├── database_connector.py      # 数据库连接器
│   └── utils.py                    # 工具函数
└── tests/                          # 测试
    ├── test_mcp_server.py
    └── test_client.py
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd e:/develop/db-ai-server
python --version  # 需要Python 3.10+
pip install -r requirements.txt
```

### 2. 配置推理引擎

db-ai-server 支持多种 AI 推理引擎，包括 **LM Studio**（推荐）和 **Ollama**。

#### 方式1：使用 LM Studio（推荐）

LM Studio 提供图形化界面，易于配置和调试。

**安装 LM Studio：**
1. 从 [lmstudio.ai](https://lmstudio.ai/) 下载并安装
2. 搜索并下载 `gemma-4-e4b-it` 模型
3. 点击 "Chat" 按钮启动推理引擎
4. 确保 "Server" 设置正确：
   - 端口: `62666`
   - CORS: `*`
   - 启用 "OpenAI Compatible API"

**配置文件：**
```json
{
  "inference_engine": {
    "type": "lmstudio",
    "base_url": "http://127.0.0.1:62666/v1",
    "model": "gemma-4-e4b-it",
    "timeout": 120,
    "max_retries": 3,
    "temperature": 0.1,
    "num_ctx": 4096,
    "num_predict": 2048
  }
}
```

#### 方式2：使用 Ollama

Ollama 是命令行工具，适合生产环境。

**安装 Ollama：**
```bash
# 访问 https://ollama.com/ 下载并安装Ollama

# 启动Ollama服务
ollama serve

# 拉取推荐模型
ollama pull gemma-4-e4b-it
# 或使用其他模型
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
```

**配置文件：**
```json
{
  "inference_engine": {
    "type": "ollama",
    "base_url": "http://127.0.0.1:11434/api",
    "model": "gemma-4-e4b-it",
    "timeout": 120,
    "max_retries": 3,
    "temperature": 0.1,
    "num_ctx": 4096,
    "num_predict": 2048
  }
}
```

#### 切换推理引擎

只需修改 `config/server_config.json` 中的 `inference_engine.type` 字段：
- `"lmstudio"` - 使用 LM Studio
- `"ollama"` - 使用 Ollama

修改后重启 db-ai-server 即可。

#### 推理引擎对比

| 特性 | LM Studio | Ollama |
|------|-----------|---------|
| 配置便捷性 | ⭐⭐⭐⭐⭐ GUI 界面 | ⭐⭐⭐ 命令行 |
| 模型管理 | ⭐⭐⭐⭐⭐ 内置市场 | ⭐⭐⭐ CLI 命令 |
| API 兼容性 | ⭐⭐⭐⭐⭐ OpenAI | ⭐⭐⭐ 自定义 |
| 资源占用 | 中等 | 较低 |
| 推荐场景 | 开发、测试 | 生产环境 |

#### 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `type` | 推理引擎类型：`lmstudio` 或 `ollama` | `lmstudio` |
| `base_url` | 推理引擎 API 地址 | `http://127.0.0.1:62666/v1` / `http://127.0.0.1:11434/api` |
| `model` | 模型名称 | `gemma-4-e4b-it` |
| `timeout` | 请求超时时间（秒） | 120 |
| `max_retries` | 最大重试次数 | 3 |
| `temperature` | 温度参数（0-1，越低越确定） | 0.1 |
| `num_ctx` | 上下文窗口大小 | 4096 |
| `num_predict` | 最大生成长度 | 2048 |

#### 测试推理引擎连接

```bash
cd e:/develop/db-ai-server
python test_engine.py
```

### 3. 配置数据库连接

编辑 `config/server_config.json`，设置 `database.connection_string`：

```json
{
  "database": {
    "schema_file": "config/database_schema.json",
    "connection_string": "mysql://root:password@localhost:3306/erack",
    "enable_direct_query": true
  }
}
```

连接字符串格式：`mysql://用户名:密码@主机:端口/数据库名`

**示例：**
```bash
# 本地MySQL
mysql://root:123456@localhost:3306/erack

# 远程MySQL
mysql://admin:secret@192.168.1.100:3306/production_db
```

### 4. 配置数据库Schema

编辑 `config/database_schema.json`，添加您的数据库表结构：

```json
{
  "database_name": "erack",
  "database_type": "mysql",
  "description": "ERack业务数据库",
  "tables": [
    {
      "name": "sys_user",
      "description": "系统用户表",
      "columns": [
        {
          "name": "id",
          "type": "bigint",
          "primary_key": true,
          "auto_increment": true,
          "description": "主键"
        },
        {
          "name": "name",
          "type": "varchar(50)",
          "required": true,
          "unique": true,
          "description": "用户名"
        },
        {
          "name": "real_name",
          "type": "varchar(50)",
          "description": "用户真实名称"
        },
        {
          "name": "role_id",
          "type": "int",
          "description": "角色Id"
        },
        {
          "name": "enable",
          "type": "int",
          "description": "是否启用"
        }
      ]
    }
  ]
}
```

### 5. 运行服务器

#### 方式1：运行MCP服务器（stdio模式）

```bash
python src/mcp_server.py
```

#### 方式2：运行HTTP桥接服务器（推荐用于Web应用）

```bash
python http_server.py
```

HTTP服务器将在 `http://0.0.0.0:8080` 启动，提供RESTful API接口。

## 📚 配置说明

所有配置文件位于 `config/` 目录：

### server_config.json
服务器基础配置（Ollama连接、日志、数据库连接等）

### database_schema.json
数据库表结构配置（最重要的配置文件）

### prompts.json
自定义提示词模板

### security_rules.json
SQL安全验证规则

## 🔧 MCP工具

### 可用工具列表

1. **get_database_schema** - 获取数据库Schema
2. **generate_sql** - 根据自然语言生成SELECT/UPDATE/INSERT/DELETE SQL
3. **validate_sql** - 验证SQL安全性
4. **estimate_rows** - 预估影响行数
5. **execute_sql** - 执行SQL并返回结果（可直接替换DAO层）
6. **get_status** - 获取服务器状态

### HTTP API接口

如果使用HTTP桥接服务器（`http_server.py`），可以通过以下REST API调用：

#### 1. 生成SQL

```http
POST /mcp/generate_sql
Content-Type: application/json

{
  "query": "查询所有用户"
}
```

**响应：**
```json
{
  "sql": "SELECT * FROM sys_user",
  "sql_type": "SELECT",
  "affected_tables": ["sys_user"],
  "estimated_rows": -1,
  "risk_level": "low",
  "explanation": "查询系统中所有用户的基本信息",
  "require_confirmation": false,
  "warnings": ["全表查询可能影响性能"],
  "suggestions": ["建议添加分页限制"],
  "validation": {
    "is_valid": true,
    "errors": [],
    "warnings": []
  }
}
```

#### 2. 执行SQL

```http
POST /mcp/execute_sql
Content-Type: application/json

{
  "sql": "SELECT * FROM sys_user"
}
```

**响应：**
```json
{
  "success": true,
  "rows": [
    {
      "id": 1,
      "name": "admin",
      "real_name": "系统用户",
      "role_id": 1,
      "enable": 1
    }
  ],
  "affectedRows": 1,
  "columns": ["id", "name", "real_name", "role_id", "enable"],
  "columnComments": {
    "id": "主键",
    "name": "用户名",
    "real_name": "用户真实名称",
    "role_id": "角色Id",
    "enable": "是否启用"
  },
  "rowCount": 1
}
```

**注意**：响应使用驼峰命名规范（columnComments、affectedRows、rowCount），方便前端使用。

## 💡 使用示例

### C#客户端集成

#### 1. 创建DbAiService

```csharp
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Logging;

namespace ERack.Common;

/// <summary>
/// DB-AI-Server 客户端服务
/// </summary>
public class DbAiService(HttpClient httpClient, ILogger<DbAiService> logger)
{
    private readonly JsonSerializerOptions jsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };
    private const string GENERATE_SQL_URL = "http://localhost:8080/mcp/generate_sql";
    private const string EXECUTE_SQL_URL = "http://localhost:8080/mcp/execute_sql";

    /// <summary>
    /// 生成SQL并执行（一步完成）
    /// </summary>
    public async Task<SqlExecutionResponse> GenerateAndExecuteAsync(string query)
    {
        // 步骤1: 生成SQL
        var generateRequest = new { query = query };
        var generateJson = JsonSerializer.Serialize(generateRequest, jsonOptions);
        var generateContent = new StringContent(generateJson, Encoding.UTF8, "application/json");

        var generateResponse = await httpClient.PostAsync(GENERATE_SQL_URL, generateContent);
        generateResponse.EnsureSuccessStatusCode();

        var generateResponseBody = await generateResponse.Content.ReadAsStringAsync();
        var generateResult = JsonSerializer.Deserialize<GenerateSqlResponse>(generateResponseBody, jsonOptions);

        if (generateResult == null || string.IsNullOrEmpty(generateResult.Sql))
        {
            return new SqlExecutionResponse { Success = false, Error = "生成SQL失败" };
        }

        // 步骤2: 执行SQL
        var executeRequest = new { sql = generateResult.Sql };
        var executeJson = JsonSerializer.Serialize(executeRequest, jsonOptions);
        var executeContent = new StringContent(executeJson, Encoding.UTF8, "application/json");

        var executeResponse = await httpClient.PostAsync(EXECUTE_SQL_URL, executeContent);
        executeResponse.EnsureSuccessStatusCode();

        var executeResponseBody = await executeResponse.Content.ReadAsStringAsync();
        var executeResult = JsonSerializer.Deserialize<SqlExecutionResponse>(executeResponseBody, jsonOptions);

        return executeResult ?? new SqlExecutionResponse { Success = false, Error = "解析执行响应失败" };
    }

    /// <summary>
    /// SQL生成响应
    /// </summary>
    public class GenerateSqlResponse
    {
        public string Sql { get; set; } = string.Empty;
        public string SqlType { get; set; } = string.Empty;
        public List<string> AffectedTables { get; set; } = new();
        public int EstimatedRows { get; set; }
        public string RiskLevel { get; set; } = string.Empty;
        public string Explanation { get; set; } = string.Empty;
        public bool RequireConfirmation { get; set; }
        public List<string> Suggestions { get; set; } = new();
        public List<string> Warnings { get; set; } = new();
    }

    /// <summary>
    /// SQL执行响应
    /// </summary>
    public class SqlExecutionResponse
    {
        [JsonPropertyName("success")]
        public bool Success { get; init; }
        
        [JsonPropertyName("rows")]
        public List<Dictionary<string, object>> Rows { get; init; } = new();
        
        [JsonPropertyName("affected_rows")]
        public int AffectedRows { get; init; }
        
        [JsonPropertyName("columns")]
        public List<string>? Columns { get; init; }
        
        [JsonPropertyName("column_comments")]
        public Dictionary<string, string>? ColumnComments { get; init; }
        
        [JsonPropertyName("row_count")]
        public int RowCount { get; init; }
        
        [JsonPropertyName("error")]
        public string? Error { get; init; }
    }
}
```

#### 2. 注册服务

```csharp
// App.xaml.cs ConfigureServices 中添加
services.AddHttpClient<DbAiService>();
```

#### 3. 使用服务

```csharp
// 查询示例
var query = "查询所有用户";
var result = await dbAiService.GenerateAndExecuteAsync(query);

if (result.Success)
{
    // 使用查询结果
    foreach (var row in result.Rows)
    {
        Console.WriteLine($"用户名: {row["name"]}");
    }

    // 获取字段注释
    if (result.ColumnComments != null)
    {
        foreach (var comment in result.ColumnComments)
        {
            Console.WriteLine($"{comment.Key}: {comment.Value}");
        }
    }
}
```

### Python客户端集成

```python
import asyncio
import json
from mcp import ClientSession, StdioServerParameters

async def generate_sql(query: str):
    async with ClientSession() as session:
        await session.connect(StdioServerParameters(
            command="python",
            args=["src/mcp_server.py"]
        ))

        result = await session.call_tool(
            "generate_sql",
            {"query": query}
        )

        return json.loads(result.content[0].text)

# 使用
sql = await generate_sql("查询所有激活的用户")
print(sql)
```

## 🎯 推荐模型

根据您的硬件配置选择合适的模型：

### RTX 4060 8GB 推荐
- **Qwen2.5-7B-Instruct** (最佳) - 中文优秀，SQL生成精准
- **Llama 3.2-3B-Instruct** - 轻量快速
- **DeepSeek-Coder-V2-Lite** - 代码生成专注

### 其他配置
- **4GB显存**: Llama 3.2-3B 或 Phi-3-mini
- **12GB+显存**: Llama 3.1-8B 或 Qwen2.5-14B

## 🔒 安全特性

1. **SQL注入防护** - 检测危险关键词和注入模式
2. **操作限制** - 仅允许UPDATE/INSERT/DELETE操作
3. **权限控制** - 基于用户上下文的细粒度权限
4. **风险评估** - 自动评估操作风险等级（Low/Medium/High/Critical）
5. **强制确认** - 高风险操作需用户确认
6. **参数化查询** - 防止SQL注入攻击

## 📊 支持的SQL操作

| 操作类型 | 功能描述 | 风险等级 |
|---------|---------|---------|
| **SELECT** | 查询数据，支持简单查询、JOIN、聚合、子查询 | Low-Medium |
| **UPDATE** | 更新数据，支持条件更新 | Medium-High |
| **INSERT** | 插入数据，支持单条和批量插入 | Low-Medium |
| **DELETE** | 删除数据，必须包含WHERE条件 | High-Critical |

## 📖 ERack系统常用查询示例

### 用户管理
```
查询所有用户
查询所有激活的用户
查询角色为operator的用户
查询用户名包含admin的用户
```

### 货架管理
```
查询所有货架信息
查询状态为在线的货架
查询E-Rack-1的所有槽位
统计每个货架的槽位占用率
```

### 统计查询
```
统计各角色的用户数量
统计每个货架的占用槽位数量
查询库存低于最低库存预警值的产品
```

## 🔍 字段注释功能

DB-AI-Server 会自动查询 `INFORMATION_SCHEMA.COLUMNS` 表获取字段的中文注释：

```sql
SELECT COLUMN_NAME, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '数据库名'
AND TABLE_NAME = '表名'
```

**注意**：
- 字段注释需要在数据库中设置（COLUMN_COMMENT）
- 如果字段没有注释，则返回字段名
- 建议为所有重要字段添加中文注释

## 📝 开发计划

- [x] HTTP桥接服务器
- [x] 字段注释查询
- [x] 驼峰命名JSON响应
- [x] LM Studio 支持
- [x] 统一推理引擎配置
- [ ] 支持更多数据库类型（PostgreSQL, Oracle等）
- [ ] 支持流式响应
- [ ] Web管理界面
- [ ] 操作审计日志
- [ ] SQL执行回滚
- [ ] 多模型切换

## 🔧 故障排除

### 问题1: "Failed to connect to inference engine"

**原因**: 推理引擎未启动或端口不正确

**解决方法**:
1. 检查 LM Studio/Ollama 是否运行
2. 检查配置中的 `base_url` 是否正确
3. 检查防火墙设置
4. 运行 `python test_engine.py` 测试连接

### 问题2: "No valid JSON found in AI response"

**原因**: 推理引擎返回了无效的响应

**解决方法**:
1. 降低 `temperature` 参数（设为 0.0 或 0.1）
2. 检查模型是否支持 JSON 输出
3. 查看 `logs/mcp_server.log` 中的完整错误信息
4. 调整提示词，明确要求只返回 JSON

### 问题3: "Model not found"

**原因**: 指定的模型未加载

**解决方法**:
- LM Studio: 在应用中加载对应模型
- Ollama: 使用 `ollama pull` 下载模型

### 问题4: 响应很慢

**原因**: 模型太大或机器性能不足

**解决方法**:
1. 使用更小的模型（如 `gemma-2b-it`）
2. 减少 `num_predict` 值
3. 增加 `timeout` 时间
4. 检查 GPU 加速是否启用

## ⚡ 性能优化

### LM Studio 优化

1. **量化**: 使用量化模型减少内存占用
2. **GPU 加速**: 确保正确配置了 CUDA/Metal
3. **上下文大小**: 根据需要调整 `num_ctx`

### Ollama 优化

1. **量化**: 使用 `OLLAMA_NUM_GPU` 环境变量
2. **批处理**: 调整 `OLLAMA_NUM_THREAD`
3. **缓存**: 启用模型缓存

### 推荐模型

根据您的硬件配置选择合适的模型：

| 显存 | 推荐模型 | 说明 |
|------|----------|------|
| RTX 4060 8GB | Qwen2.5-7B-Instruct | 中文优秀，SQL生成精准 |
| 4GB | Llama 3.2-3B-Instruct / Phi-3-mini | 轻量快速 |
| 12GB+ | Llama 3.1-8B / Qwen2.5-14B | 更高质量输出 |

## 📊 监控与日志

### 查看服务器状态

```bash
# 通过 API 查询
curl http://localhost:8080/mcp/get_server_status

# 或在 ERack 中
# 菜单 "通用查询" -> "AI查询" -> 查看状态
```

### 查看详细日志

```bash
tail -f db-ai-server/logs/mcp_server.log
```

日志会记录：
- 推理引擎连接状态
- SQL 生成和执行过程
- AI 原始响应（前500字符）
- 错误和警告信息

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 📞 联系方式

**Made with ❤️ for db-ai-server MCP integration**
