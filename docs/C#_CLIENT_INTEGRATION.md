# C#/.NET 集成指南 - LangChain 智能代理系统

## 📖 概述

本文档详细说明如何在 C#/.NET 项目中集成 DB-AI-Server 的智能代理系统，实现通过自然语言完成复杂的多步数据库操作。

**技术栈**：基于 LangChain + LangGraph 开发平台

## 🎯 核心优势

### LangChain Agent 系统
- **ReAct 策略**：推理(Reasoning) + 行动(Action) 的循环模式
- **自动多步规划**：AI自主分析用户意图，自动规划完整的操作流程
- **智能工具调用**：根据推理结果动态调用合适的工具
- **完整数据返回**：INSERT/UPDATE后自动查询并返回最新数据

### 开发效率提升
- **无需编写数据访问层**：通过自然语言描述直接完成复杂操作
- **智能查询优化**：自动提供性能优化建议
- **安全可控**：多层验证、风险评估、权限控制
- **快速开发**：界面用户输入 → LangChain Agent → 完整结果，开发效率大幅提升

## 🚀 LangChain Agent 功能

### Agent 架构
- **Reasoning** - 推理用户意图，选择合适的工具
- **Action** - 执行工具并获取结果
- **Observation** - 观察结果，决定下一步行动
- **Memory** - 记忆对话历史，保持上下文连贯性

### 可用工具（LangChain Tools）：
1. `execute_sql` - 执行SQL语句（SELECT/INSERT/UPDATE/DELETE）
2. `query_data` - 查询数据库数据
3. `get_schema` - 获取数据库表结构
4. `validate_sql` - 验证SQL安全性
5. `generate_sql` - 生成SQL语句
6. `analyze_results` - 分析查询结果

## 📡 C#客户端调用方式

### 1. 使用 `execute_intelligently` 工具（主要入口）

这是C#客户端应该使用的主要工具，AI会自动规划完整的操作流程：

```json
{
  "name": "execute_intelligently",
  "description": "智能执行：AI自主分析用户意图，自动规划多步操作（数据变更后自动验证）",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string", 
        "description": "用户自然语言描述"
      }
    },
    "required": ["query"]
  }
}
```

### 2. 智能代理执行流程

**插入数据并返回查询结果的完整流程：**
```json
{
  "query": "添加用户yh，真实姓名yunhai，密码123，角色ID为1"
}
```

**AI会自动执行以下步骤：**
1. 📝 AI理解用户意图 → INSERT操作
2. 🔧 生成INSERT SQL语句
3. ⚡ 执行INSERT操作
4. 🔍 自动生成验证查询
5. 📊 执行验证查询
6. ✅ 返回新插入的数据

### 3. 返回结果格式（LangChain Agent）

```json
{
  "success": true,
  "agent_type": "langchain",
  "response": "INSERT操作成功，已添加新用户yh",
  "intermediate_steps": [
    {"tool": "generate_sql", "input": "添加用户yh", "output": "INSERT INTO ..."},
    {"tool": "execute_sql", "input": "INSERT INTO ...", "output": "affected_rows: 1"}
  ],
  "memory_summary": [
    {"timestamp": "2026-04-13T10:00:00", "content": "用户请求: 添加用户yh"}
  ]
}
```

### 4. 其他操作示例

**查询数据：**
```json
{
  "query": "查询所有可用的用户"
}
```

**更新数据：**
```json
{
  "query": "修改用户yh的状态为不可用"
}
```

## 🔧 基础集成方式

### 方式1：HTTP API（推荐）

最简单的方式是通过HTTP调用MCP Server。

#### 1. 安装依赖

```xml
<ItemGroup>
    <PackageReference Include="System.Text.Json" Version="8.0.0" />
    <PackageReference Include="Microsoft.Extensions.Http" Version="8.0.0" />
</ItemGroup>
```

#### 2. 创建请求/响应模型

```csharp
using System.Text.Json.Serialization;

namespace ERack.Services.DbAi
{
    /// <summary>
    /// SQL生成请求
    /// </summary>
    public class SqlGenerationRequest
    {
        [JsonPropertyName("tool")]
        public string Tool { get; set; } = "generate_sql";

        [JsonPropertyName("arguments")]
        public SqlGenerationArguments Arguments { get; set; } = new();
    }

    /// <summary>
    /// SQL生成参数
    /// </summary>
    public class SqlGenerationArguments
    {
        /// <summary>
        /// 自然语言查询描述
        /// </summary>
        [JsonPropertyName("query")]
        public string Query { get; set; } = string.Empty;

        /// <summary>
        /// 用户上下文信息
        /// </summary>
        [JsonPropertyName("user_context")]
        public UserContext? UserContext { get; set; }
    }

    /// <summary>
    /// 智能执行参数
    /// </summary>
    public class IntelligentExecutionArguments
    {
        /// <summary>
        /// 自然语言查询描述
        /// </summary>
        [JsonPropertyName("query")]
        public string Query { get; set; } = string.Empty;
    }

    /// <summary>
    /// 智能执行响应
    /// </summary>
    public class IntelligentExecutionResponse
    {
        /// <summary>
        /// 是否执行成功
        /// </summary>
        [JsonPropertyName("success")]
        public bool Success { get; set; }

        /// <summary>
        /// 操作类型
        /// </summary>
        [JsonPropertyName("operation")]
        public string Operation { get; set; } = string.Empty;

        /// <summary>
        /// 用户原始查询
        /// </summary>
        [JsonPropertyName("user_query")]
        public string UserQuery { get; set; } = string.Empty;

        /// <summary>
        /// 执行摘要
        /// </summary>
        [JsonPropertyName("execution_summary")]
        public ExecutionSummary? ExecutionSummary { get; set; }

        /// <summary>
        /// 是否有可用数据
        /// </summary>
        [JsonPropertyName("data_available")]
        public bool DataAvailable { get; set; }

        /// <summary>
        /// 返回的数据
        /// </summary>
        [JsonPropertyName("data")]
        public List<Dictionary<string, object>> Data { get; set; } = new();

        /// <summary>
        /// 操作消息
        /// </summary>
        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;

        /// <summary>
        /// 是否完成完整工作流
        /// </summary>
        [JsonPropertyName("complete_workflow")]
        public bool CompleteWorkflow { get; set; }

        /// <summary>
        /// 工作流步骤
        /// </summary>
        [JsonPropertyName("workflow_steps")]
        public List<string> WorkflowSteps { get; set; } = new();
    }

    /// <summary>
    /// 执行摘要
    /// </summary>
    public class ExecutionSummary
    {
        [JsonPropertyName("sql_generated")]
        public string SqlGenerated { get; set; } = string.Empty;

        [JsonPropertyName("sql_executed")]
        public string SqlExecuted { get; set; } = string.Empty;

        [JsonPropertyName("affected_rows")]
        public int AffectedRows { get; set; }

        [JsonPropertyName("insert_id")]
        public long? InsertId { get; set; }

        [JsonPropertyName("row_count")]
        public int RowCount { get; set; }
    }

    /// <summary>
    /// 用户上下文
    /// </summary>
    public class UserContext
    {
        [JsonPropertyName("username")]
        public string? Username { get; set; }

        [JsonPropertyName("role")]
        public string? Role { get; set; }

        [JsonPropertyName("permissions")]
        public List<string>? Permissions { get; set; }
    }

    /// <summary>
    /// SQL生成响应
    /// </summary>
    public class SqlGenerationResponse
    {
        /// <summary>
        /// 生成的SQL语句
        /// </summary>
        [JsonPropertyName("sql")]
        public string Sql { get; set; } = string.Empty;

        /// <summary>
        /// SQL类型：SELECT/UPDATE/INSERT/DELETE
        /// </summary>
        [JsonPropertyName("sql_type")]
        public string SqlType { get; set; } = string.Empty;

        /// <summary>
        /// 受影响的表名列表
        /// </summary>
        [JsonPropertyName("affected_tables")]
        public List<string> AffectedTables { get; set; } = new();

        /// <summary>
        /// 预估影响行数
        /// </summary>
        [JsonPropertyName("estimated_rows")]
        public int EstimatedRows { get; set; }

        /// <summary>
        /// 风险等级：low/medium/high/critical
        /// </summary>
        [JsonPropertyName("risk_level")]
        public string RiskLevel { get; set; } = string.Empty;

        /// <summary>
        /// 操作说明
        /// </summary>
        [JsonPropertyName("explanation")]
        public string Explanation { get; set; } = string.Empty;

        /// <summary>
        /// 是否需要用户确认
        /// </summary>
        [JsonPropertyName("require_confirmation")]
        public bool RequireConfirmation { get; set; }

        /// <summary>
        /// 警告信息列表
        /// </summary>
        [JsonPropertyName("warnings")]
        public List<string> Warnings { get; set; } = new();

        /// <summary>
        /// 查询类型（SELECT操作）：simple/join/aggregate/subquery
        /// </summary>
        [JsonPropertyName("query_type")]
        public string? QueryType { get; set; }

        /// <summary>
        /// 优化建议列表
        /// </summary>
        [JsonPropertyName("suggestions")]
        public List<string> Suggestions { get; set; } = new();

        /// <summary>
        /// 验证结果
        /// </summary>
        [JsonPropertyName("validation")]
        public ValidationResult? Validation { get; set; }
    }

    /// <summary>
    /// 验证结果
    /// </summary>
    public class ValidationResult
    {
        [JsonPropertyName("is_valid")]
        public bool IsValid { get; set; }

        [JsonPropertyName("errors")]
        public List<string> Errors { get; set; } = new();

        [JsonPropertyName("warnings")]
        public List<string> Warnings { get; set; } = new();

        [JsonPropertyName("sql_type")]
        public string? SqlType { get; set; }
    }

    /// <summary>
    /// SQL执行响应
    /// </summary>
    public class SqlExecutionResponse
    {
        /// <summary>
        /// 是否执行成功
        /// </summary>
        [JsonPropertyName("success")]
        public bool Success { get; set; }

        /// <summary>
        /// 查询结果行（SELECT操作）
        /// </summary>
        [JsonPropertyName("rows")]
        public List<Dictionary<string, object>> Rows { get; set; } = new();

        /// <summary>
        /// 影响行数
        /// </summary>
        [JsonPropertyName("affected_rows")]
        public int AffectedRows { get; set; }

        /// <summary>
        /// 列名列表（SELECT操作）
        /// </summary>
        [JsonPropertyName("columns")]
        public List<string>? Columns { get; set; }

        /// <summary>
        /// 字段注释字典（用于DataGrid列头显示）
        /// 格式：{字段名: 注释}
        /// </summary>
        [JsonPropertyName("column_comments")]
        public Dictionary<string, string>? ColumnComments { get; set; }

        /// <summary>
        /// 返回行数（SELECT操作）
        /// </summary>
        [JsonPropertyName("row_count")]
        public int RowCount { get; set; }

        /// <summary>
        /// 插入的ID（INSERT操作）
        /// </summary>
        [JsonPropertyName("insert_id")]
        public long? InsertId { get; set; }

        /// <summary>
        /// 错误信息
        /// </summary>
        [JsonPropertyName("error")]
        public string? Error { get; set; }
    }
}
```

#### 3. 创建服务类

```csharp
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging;

namespace ERack.Services.DbAi
{
    /// <summary>
    /// DB-AI-Server客户端服务
    /// </summary>
    public class DbAiService
    {
        private readonly HttpClient _httpClient;
        private readonly string _serverUrl;
        private readonly ILogger<DbAiService> _logger;
        private readonly JsonSerializerOptions _jsonOptions;

        public DbAiService(
            HttpClient httpClient,
            IConfiguration configuration,
            ILogger<DbAiService> logger)
        {
            _httpClient = httpClient;
            _serverUrl = configuration["DbAiServer:Url"] ?? "http://localhost:8080/mcp";
            _logger = logger;
            _jsonOptions = new JsonSerializerOptions
            {
                PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            };
        }

        /// <summary>
        /// 智能执行 - 主要入口
        /// </summary>
        /// <param name="query">自然语言描述</param>
        /// <returns>智能执行响应，包含完整操作结果和返回的数据</returns>
        public async Task<IntelligentExecutionResponse> ExecuteIntelligentlyAsync(string query)
        {
            var request = new Dictionary<string, object>
            {
                ["tool"] = "execute_intelligently",
                ["arguments"] = new IntelligentExecutionArguments
                {
                    Query = query
                }
            };

            var json = JsonSerializer.Serialize(request, _jsonOptions);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            try
            {
                _logger.LogInformation("向DB-AI-Server发送智能执行请求: {Query}", query);

                var response = await _httpClient.PostAsync(_serverUrl, content);
                response.EnsureSuccessStatusCode();

                var responseBody = await response.Content.ReadAsStringAsync();

                // MCP协议返回格式需要解析
                var mcpResponse = JsonSerializer.Deserialize<McpResponse>(responseBody, _jsonOptions);

                if (mcpResponse?.Content?.FirstOrDefault()?.Text != null)
                {
                    var intelligentResponse = JsonSerializer.Deserialize<IntelligentExecutionResponse>(
                        mcpResponse.Content[0].Text,
                        _jsonOptions
                    );

                    _logger.LogInformation("智能执行完成: {Operation} - {Success}",
                        intelligentResponse?.Operation, intelligentResponse?.Success);

                    return intelligentResponse!;
                }

                throw new InvalidOperationException("无效的响应格式");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "智能执行失败");
                throw;
            }
        }

        /// <summary>
        /// 根据自然语言生成SQL
        /// </summary>
        /// <param name="query">自然语言描述</param>
        /// <param name="username">当前用户名</param>
        /// <param name="role">用户角色</param>
        /// <param name="permissions">用户权限列表</param>
        /// <returns>生成的SQL响应</returns>
        public async Task<SqlGenerationResponse> GenerateSqlAsync(
            string query,
            string? username = null,
            string? role = null,
            List<string>? permissions = null)
        {
            var request = new SqlGenerationRequest
            {
                Arguments = new SqlGenerationArguments
                {
                    Query = query,
                    UserContext = new UserContext
                    {
                        Username = username,
                        Role = role,
                        Permissions = permissions
                    }
                }
            };

            var json = JsonSerializer.Serialize(request, _jsonOptions);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            try
            {
                _logger.LogInformation("向DB-AI-Server发送SQL生成请求: {Query}", query);

                var response = await _httpClient.PostAsync(_serverUrl, content);
                response.EnsureSuccessStatusCode();

                var responseBody = await response.Content.ReadAsStringAsync();

                // MCP协议返回格式需要解析
                var mcpResponse = JsonSerializer.Deserialize<McpResponse>(responseBody, _jsonOptions);

                if (mcpResponse?.Content?.FirstOrDefault()?.Text != null)
                {
                    var sqlResponse = JsonSerializer.Deserialize<SqlGenerationResponse>(
                        mcpResponse.Content[0].Text,
                        _jsonOptions
                    );

                    _logger.LogInformation("SQL生成成功: {SqlType} - {RiskLevel}",
                        sqlResponse?.SqlType, sqlResponse?.RiskLevel);

                    return sqlResponse!;
                }

                throw new InvalidOperationException("无效的响应格式");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "SQL生成失败");
                throw;
            }
        }

        /// <summary>
        /// 获取数据库Schema
        /// </summary>
        /// <param name="tableName">表名（可选）</param>
        /// <returns>Schema信息</returns>
        public async Task<string> GetSchemaAsync(string? tableName = null)
        {
            var request = new Dictionary<string, object>
            {
                ["tool"] = "get_database_schema",
                ["arguments"] = new
                {
                    table_name = tableName
                }
            };

            var json = JsonSerializer.Serialize(request, _jsonOptions);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync(_serverUrl, content);
            response.EnsureSuccessStatusCode();

            return await response.Content.ReadAsStringAsync();
        }

        /// <summary>
        /// 验证SQL安全性
        /// </summary>
        public async Task<string> ValidateSqlAsync(string sql)
        {
            var request = new Dictionary<string, object>
            {
                ["tool"] = "validate_sql",
                ["arguments"] = new
                {
                    sql = sql
                }
            };

            var json = JsonSerializer.Serialize(request, _jsonOptions);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync(_serverUrl, content);
            response.EnsureSuccessStatusCode();

            return await response.Content.ReadAsStringAsync();
        }

        /// <summary>
        /// 执行SQL语句（直接替换DAO层）
        /// </summary>
        /// <param name="sql">SQL语句</param>
        /// <param name="parameters">SQL参数（防止SQL注入）</param>
        /// <returns>执行结果</returns>
        public async Task<SqlExecutionResponse> ExecuteSqlAsync(
            string sql,
            object[]? parameters = null)
        {
            var request = new Dictionary<string, object>
            {
                ["tool"] = "execute_sql",
                ["arguments"] = new
                {
                    sql = sql,
                    @params = parameters ?? Array.Empty<object>()
                }
            };

            var json = JsonSerializer.Serialize(request, _jsonOptions);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            try
            {
                _logger.LogInformation("向DB-AI-Server发送SQL执行请求: {Sql}", sql);

                var response = await _httpClient.PostAsync(_serverUrl, content);
                response.EnsureSuccessStatusCode();

                var responseBody = await response.Content.ReadAsStringAsync();
                var mcpResponse = JsonSerializer.Deserialize<McpResponse>(responseBody, _jsonOptions);

                if (mcpResponse?.Content?.FirstOrDefault()?.Text != null)
                {
                    var execResponse = JsonSerializer.Deserialize<SqlExecutionResponse>(
                        mcpResponse.Content[0].Text,
                        _jsonOptions
                    );

                    if (execResponse?.Success == true)
                    {
                        _logger.LogInformation("SQL执行成功，影响行数: {AffectedRows}", execResponse.AffectedRows);
                    }
                    else
                    {
                        _logger.LogWarning("SQL执行失败: {Error}", execResponse?.Error);
                    }

                    return execResponse!;
                }

                throw new InvalidOperationException("无效的响应格式");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "SQL执行失败");
                throw;
            }
        }

        /// <summary>
        /// 生成SQL并执行（一步完成，替代完整数据访问层）
        /// </summary>
        /// <param name="query">自然语言描述</param>
        /// <param name="username">当前用户名</param>
        /// <param name="role">用户角色</param>
        /// <returns>执行结果</returns>
        public async Task<SqlExecutionResponse> GenerateAndExecuteAsync(
            string query,
            string? username = null,
            string? role = null)
        {
            // 步骤1: 生成SQL
            var sqlResponse = await GenerateSqlAsync(query, username, role);

            if (sqlResponse.RequireConfirmation)
            {
                _logger.LogWarning("SQL需要确认后再执行: {Reason}", sqlResponse.Explanation);
            }

            // 步骤2: 执行SQL
            return await ExecuteSqlAsync(sqlResponse.Sql);
        }
    }

    /// <summary>
    /// MCP协议响应格式
    /// </summary>
    public class McpResponse
    {
        [JsonPropertyName("content")]
        public List<McpContentItem>? Content { get; set; }
    }

    public class McpContentItem
    {
        [JsonPropertyName("type")]
        public string Type { get; set; } = "text";

        [JsonPropertyName("text")]
        public string Text { get; set; } = string.Empty;
    }
}
```

#### 4. 注册服务

在 `Program.cs` 或 `Startup.cs` 中注册服务：

```csharp
// 注册DB-AI服务
builder.Services.AddHttpClient<DbAiService>();
```

在 `appsettings.json` 中添加配置：

```json
{
  "DbAiServer": {
    "Url": "http://localhost:8080/mcp"
  }
}
```

#### 5. 在ViewModel中使用智能代理

```csharp
using System.Windows;
using System.Windows.Input;
using ERack.Services.DbAi;

namespace ERack.ViewModels
{
    /// <summary>
    /// 用户管理视图模型
    /// </summary>
    public class UserViewModel : ViewModelBase
    {
        private readonly DbAiService _dbAiService;
        private readonly DialogBox _dialogBox;

        private string _naturalQuery = string.Empty;
        public string NaturalQuery
        {
            get => _naturalQuery;
            set => SetProperty(ref _naturalQuery, value);
        }

        private List<UserInfo> _userList = new();
        public List<UserInfo> UserList
        {
            get => _userList;
            set => SetProperty(ref _userList, value);
        }

        public ICommand QueryCommand { get; }
        public ICommand UpdateCommand { get; }

        public UserViewModel(
            DbAiService dbAiService,
            DialogBox dialogBox)
        {
            _dbAiService = dbAiService;
            _dialogBox = dialogBox;

            QueryCommand = new RelayCommand(async () => await ExecuteIntelligentQueryAsync());
            UpdateCommand = new RelayCommand(async () => await ExecuteIntelligentUpdateAsync());
        }

        /// <summary>
        /// 使用智能代理执行查询（推荐：自动规划完整流程）
        /// </summary>
        private async Task ExecuteIntelligentQueryAsync()
        {
            if (string.IsNullOrWhiteSpace(NaturalQuery))
            {
                _dialogBox.ShowDialog("提示", "请输入查询条件", DialogIconEnum.Warning);
                return;
            }

            try
            {
                // 使用智能代理系统
                var result = await _dbAiService.ExecuteIntelligentlyAsync(NaturalQuery);

                if (!result.Success)
                {
                    _dialogBox.ShowDialog("错误", $"操作失败：{result.Message}", DialogIconEnum.Error);
                    return;
                }

                // 处理返回的数据
                if (result.DataAvailable && result.Data.Count > 0)
                {
                    // 将返回的字典列表转换为 UserInfo 对象
                    var users = result.Data.Select(row => new UserInfo
                    {
                        Id = Convert.ToInt64(row.GetValueOrDefault("id")),
                        Username = row.GetValueOrDefault("username")?.ToString(),
                        Nickname = row.GetValueOrDefault("nickname")?.ToString(),
                        Email = row.GetValueOrDefault("email")?.ToString(),
                        Status = row.GetValueOrDefault("status")?.ToString()
                    }).ToList();

                    UserList = users;

                    // 显示完整工作流信息
                    string workflowInfo = "";
                    if (result.WorkflowSteps.Count > 0)
                    {
                        workflowInfo = $"\n\nAI执行步骤:\n{string.Join("\n", result.WorkflowSteps.Select((step, i) => $"{i + 1}. {step}"))}";
                    }

                    _dialogBox.ShowDialog("成功",
                        $"{result.Message}{workflowInfo}",
                        DialogIconEnum.Info);
                }
                else
                {
                    _dialogBox.ShowDialog("提示", $"{result.Message}（无数据返回）", DialogIconEnum.Warning);
                }
            }
            catch (Exception ex)
            {
                _dialogBox.ShowDialog("错误", $"操作失败：{ex.Message}", DialogIconEnum.Error);
            }
        }

        /// <summary>
        /// 使用智能代理执行更新/插入
        /// </summary>
        private async Task ExecuteIntelligentUpdateAsync()
        {
            if (string.IsNullOrWhiteSpace(NaturalQuery))
            {
                _dialogBox.ShowDialog("提示", "请输入更新指令", DialogIconEnum.Warning);
                return;
            }

            try
            {
                // 使用智能代理系统
                var result = await _dbAiService.ExecuteIntelligentlyAsync(NaturalQuery);

                if (!result.Success)
                {
                    _dialogBox.ShowDialog("错误", $"操作失败：{result.Message}", DialogIconEnum.Error);
                    return;
                }

                // 显示完整结果
                string resultInfo = result.Message;
                if (result.ExecutionSummary != null)
                {
                    resultInfo += $"\n影响行数: {result.ExecutionSummary.AffectedRows}";
                    if (result.ExecutionSummary.InsertId != null)
                    {
                        resultInfo += $"\n新增ID: {result.ExecutionSummary.InsertId}";
                    }
                }

                if (result.WorkflowSteps.Count > 0)
                {
                    resultInfo += $"\n\nAI执行步骤:\n{string.Join("\n", result.WorkflowSteps.Select((step, i) => $"{i + 1}. {step}"))}";
                }

                _dialogBox.ShowDialog("成功", resultInfo, DialogIconEnum.Info);
            }
            catch (Exception ex)
            {
                _dialogBox.ShowDialog("错误", $"操作失败：{ex.Message}", DialogIconEnum.Error);
            }
        }
    }

    /// <summary>
    /// 用户信息
    /// </summary>
    public class UserInfo
    {
        public long Id { get; set; }
        public string? Username { get; set; }
        public string? Nickname { get; set; }
        public string? Email { get; set; }
        public string? Status { get; set; }
    }
}
```

## 🏃 系统运行方式

### 启动MCP服务器（stdio模式）：
```bash
python src/mcp_server.py
```

### 启动HTTP服务器（REST API）：
```bash
python http_server.py
```
默认地址：http://0.0.0.0:8080

## ✅ 验证测试

您可以使用以下自然语言查询测试智能代理系统：

1. **添加用户**: "添加一个测试用户，姓名为testuser"
2. **查询用户**: "查看所有用户"
3. **更新状态**: "修改testuser的状态为不可用"
4. **复杂查询**: "查询system角色的功能模块访问权限"

系统将自动完成整个流程，并返回操作结果和查询数据。

## 🔧 MCP客户端完整实现（备用）

如果您需要直接使用MCP客户端而不是HTTP API，可以参考以下实现：

```csharp
using System.Text.Json;
using System.Text.Json.Serialization;

namespace DbAiServerMcpClient;

/// <summary>
/// MCP客户端实现
/// </summary>
public class McpClient : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly string _serverUrl;
    private bool _disposed;

    public McpClient(string serverUrl = "http://localhost:8080")
    {
        _httpClient = new HttpClient();
        _serverUrl = serverUrl;
    }

    /// <summary>
    /// 智能执行
    /// </summary>
    public async Task<IntelligentExecutionResponse> ExecuteIntelligentlyAsync(string query)
    {
        var request = new McpRequest
        {
            Tool = "execute_intelligently",
            Arguments = new IntelligentExecutionArguments
            {
                Query = query
            }
        };

        var response = await SendRequestAsync(request);
        var result = JsonSerializer.Deserialize<IntelligentExecutionResponse>(
            response.Content,
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });

        return result ?? throw new InvalidOperationException("Failed to parse response");
    }

    /// <summary>
    /// 生成SQL
    /// </summary>
    public async Task<SqlGenerationResponse> GenerateSqlAsync(
        string query,
        UserContext? userContext = null)
    {
        var request = new McpRequest
        {
            Tool = "generate_sql",
            Arguments = new SqlGenerationArguments
            {
                Query = query,
                UserContext = userContext
            }
        };

        var response = await SendRequestAsync(request);
        var result = JsonSerializer.Deserialize<SqlGenerationResponse>(
            response.Content,
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });

        return result ?? throw new InvalidOperationException("Failed to parse response");
    }

    /// <summary>
    /// 获取数据库Schema
    /// </summary>
    public async Task<DatabaseSchema> GetSchemaAsync(string? tableName = null)
    {
        var request = new McpRequest
        {
            Tool = "get_database_schema",
            Arguments = new SchemaArguments
            {
                TableName = tableName
            }
        };

        var response = await SendRequestAsync(request);
        var schema = JsonSerializer.Deserialize<DatabaseSchema>(
            response.Content,
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });

        return schema ?? throw new InvalidOperationException("Failed to parse schema");
    }

    /// <summary>
    /// 验证SQL
    /// </summary>
    public async Task<ValidationResult> ValidateSqlAsync(string sql)
    {
        var request = new McpRequest
        {
            Tool = "validate_sql",
            Arguments = new ValidateSqlArguments
            {
                Sql = sql
            }
        };

        var response = await SendRequestAsync(request);
        var result = JsonSerializer.Deserialize<ValidationResult>(
            response.Content,
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });

        return result ?? throw new InvalidOperationException("Failed to parse validation result");
    }

    /// <summary>
    /// 预估影响行数
    /// </summary>
    public async Task<EstimationResult> EstimateAffectedRowsAsync(string sql)
    {
        var request = new McpRequest
        {
            Tool = "estimate_affected_rows",
            Arguments = new EstimateRowsArguments
            {
                Sql = sql
            }
        };

        var response = await SendRequestAsync(request);
        var result = JsonSerializer.Deserialize<EstimationResult>(
            response.Content,
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });

        return result ?? throw new InvalidOperationException("Failed to parse estimation result");
    }

    /// <summary>
    /// 获取服务器状态
    /// </summary>
    public async Task<ServerStatus> GetServerStatusAsync()
    {
        var request = new McpRequest
        {
            Tool = "get_server_status",
            Arguments = new { }
        };

        var response = await SendRequestAsync(request);
        var status = JsonSerializer.Deserialize<ServerStatus>(
            response.Content,
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });

        return status ?? throw new InvalidOperationException("Failed to parse server status");
    }

    private async Task<McpResponse> SendRequestAsync(McpRequest request)
    {
        var json = JsonSerializer.Serialize(request);
        var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync($"{_serverUrl}/mcp", content);
        response.EnsureSuccessStatusCode();

        var responseContent = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<McpResponse>(responseContent) 
            ?? throw new InvalidOperationException("Failed to parse MCP response");
    }

    public void Dispose()
    {
        if (!_disposed)
        {
            _httpClient.Dispose();
            _disposed = true;
        }
    }
}

#region 数据模型

public class McpRequest
{
    [JsonPropertyName("tool")]
    public string Tool { get; set; } = string.Empty;

    [JsonPropertyName("arguments")]
    public object? Arguments { get; set; }
}

public class McpResponse
{
    [JsonPropertyName("content")]
    public string Content { get; set; } = string.Empty;

    [JsonPropertyName("isError")]
    public bool IsError { get; set; }
}

public class SchemaArguments
{
    [JsonPropertyName("table_name")]
    public string? TableName { get; set; }
}

public class ValidateSqlArguments
{
    [JsonPropertyName("sql")]
    public string Sql { get; set; } = string.Empty;
}

public class EstimateRowsArguments
{
    [JsonPropertyName("sql")]
    public string Sql { get; set; } = string.Empty;
}

public class EstimationResult
{
    [JsonPropertyName("estimated_rows")]
    public int EstimatedRows { get; set; }
}

public class DatabaseSchema
{
    [JsonPropertyName("database_name")]
    public string DatabaseName { get; set; } = string.Empty;

    [JsonPropertyName("database_type")]
    public string DatabaseType { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("tables")]
    public List<TableSchema> Tables { get; set; } = new();
}

public class TableSchema
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("columns")]
    public List<ColumnSchema> Columns { get; set; } = new();
}

public class ColumnSchema
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    [JsonPropertyName("required")]
    public bool Required { get; set; }

    [JsonPropertyName("unique")]
    public bool Unique { get; set; }

    [JsonPropertyName("primary_key")]
    public bool PrimaryKey { get; set; }

    [JsonPropertyName("description")]
    public string? Description { get; set; }
}

public class ServerStatus
{
    [JsonPropertyName("server")]
    public ServerInfo Server { get; set; } = new();

    [JsonPropertyName("ollama")]
    public OllamaInfo Ollama { get; set; } = new();

    [JsonPropertyName("database")]
    public DatabaseInfo Database { get; set; } = new();
}

public class ServerInfo
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("version")]
    public string Version { get; set; } = string.Empty;

    [JsonPropertyName("started_at")]
    public string StartedAt { get; set; } = string.Empty;
}

public class OllamaInfo
{
    [JsonPropertyName("model")]
    public string Model { get; set; } = string.Empty;

    [JsonPropertyName("base_url")]
    public string BaseUrl { get; set; } = string.Empty;

    [JsonPropertyName("connected")]
    public bool Connected { get; set; }
}

public class DatabaseInfo
{
    [JsonPropertyName("database_name")]
    public string DatabaseName { get; set; } = string.Empty;

    [JsonPropertyName("database_type")]
    public string DatabaseType { get; set; } = string.Empty;

    [JsonPropertyName("tables_count")]
    public int TablesCount { get; set; }
}

#endregion
```

## 🛠️ 系统配置确认

### 当前系统状态：
- **数据库连接**: ✅ 正常 (erack @ localhost:3306)
- **AI推理引擎**: ✅ 正常 (LM Studio + qwen2.5-coder-3b-instruct)
- **LangChain Agent**: ✅ 已初始化 (基于 LangChain v0.3+)
- **MCP服务器**: ✅ 运行正常

### LangChain 依赖：
```
langchain>=0.3.0
langchain-core>=0.3.0
langchain-community>=0.3.0
langgraph>=0.2.0
```

## 🏆 最佳实践

1. **优先使用 LangChain Agent**：C#客户端应优先调用`execute_intelligently`工具
2. **处理中间步骤**：展示 LangChain Agent 的推理过程，增强用户体验
3. **数据展示优化**：使用返回的字段注释优化DataGrid列头显示
4. **错误处理完整**：捕获并显示完整的错误信息和工作流状态
5. **日志记录**：记录所有智能代理操作，便于问题排查

## 📋 C#客户端代码示例（简化版）

```csharp
// 调用智能执行工具的示例代码
public async Task<JObject> ExecuteIntelligentlyAsync(string userQuery)
{
    var request = new
    {
        name = "execute_intelligently",
        arguments = new
        {
            query = userQuery
        }
    };
    
    // 发送请求到MCP服务器
    var response = await SendMcpRequestAsync(request);
    
    // 解析响应
    var result = JObject.Parse(response);
    
    // 检查操作是否成功
    if (result["success"]?.Value<bool>() == true)
    {
        // 获取返回的数据
        var data = result["data"]?.ToObject<List<JObject>>();
        if (data != null && data.Count > 0)
        {
            // 显示数据给用户
            DisplayDataToUser(data);
        }
    }
    
    return result;
}
```

---

**总结**: 现在C#客户端只需要调用`execute_intelligently`工具，传入自然语言查询，系统就会使用 LangChain Agent 自动完成所有步骤并返回完整数据和操作结果。

**技术升级**: 系统已从原生 Agent 迁移到 LangChain 开发平台，享受更强大的 Agent 框架和工具调用能力！