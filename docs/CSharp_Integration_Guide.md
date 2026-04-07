# C#/.NET 集成指南

## 概述

本文档详细说明如何在 C#/.NET 项目中集成 DB-AI-Server，实现通过自然语言生成SQL查询、更新、插入和删除操作。

## 核心优势

- **无需编写数据访问层**：通过自然语言描述直接生成SQL，无需创建DAO、Repository等数据访问对象
- **智能查询优化**：自动提供性能优化建议
- **安全可控**：多层验证、风险评估、权限控制
- **快速开发**：界面用户输入 → 提示词 → SQL，开发效率大幅提升

## 集成方式

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
        /// <param name="params">SQL参数（防止SQL注入）</param>
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
                    params = parameters ?? Array.Empty<object>()
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

#### 5. 在ViewModel中使用

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

            QueryCommand = new RelayCommand(async () => await ExecuteQueryAsync());
            UpdateCommand = new RelayCommand(async () => await ExecuteUpdateAsync());
        }

        /// <summary>
        /// 执行查询（推荐：使用 execute_sql 直接执行，无需DbContext）
        /// </summary>
        private async Task ExecuteQueryAsync()
        {
            if (string.IsNullOrWhiteSpace(NaturalQuery))
            {
                _dialogBox.ShowDialog("提示", "请输入查询条件", DialogIconEnum.Warning);
                return;
            }

            try
            {
                // 方式1: 使用 GenerateAndExecuteAsync（一步完成，最简单）
                var result = await _dbAiService.GenerateAndExecuteAsync(
                    NaturalQuery,
                    "admin",
                    "administrator"
                );

                if (!result.Success)
                {
                    _dialogBox.ShowDialog("错误", $"查询失败：{result.Error}", DialogIconEnum.Error);
                    return;
                }

                // 处理SELECT查询结果
                if (result.Rows.Count > 0)
                {
                    // 将返回的字典列表转换为 UserInfo 对象
                    var users = result.Rows.Select(row => new UserInfo
                    {
                        Id = Convert.ToInt64(row.GetValueOrDefault("id")),
                        Username = row.GetValueOrDefault("username")?.ToString(),
                        Nickname = row.GetValueOrDefault("nickname")?.ToString(),
                        Email = row.GetValueOrDefault("email")?.ToString(),
                        Status = row.GetValueOrDefault("status")?.ToString()
                    }).ToList();

                    UserList = users;

                    _dialogBox.ShowDialog("成功",
                        $"查询成功，返回 {result.RowCount} 行数据",
                        DialogIconEnum.Info);
                }
                else
                {
                    _dialogBox.ShowDialog("提示", "没有查询到数据", DialogIconEnum.Warning);
                }
            }
            catch (Exception ex)
            {
                _dialogBox.ShowDialog("错误", $"查询失败：{ex.Message}", DialogIconEnum.Error);
            }
        }

        /// <summary>
        /// 执行更新/插入/删除
        /// </summary>
        private async Task ExecuteUpdateAsync()
        {
            if (string.IsNullOrWhiteSpace(NaturalQuery))
            {
                _dialogBox.ShowDialog("提示", "请输入更新指令", DialogIconEnum.Warning);
                return;
            }

            try
            {
                // 使用 GenerateAndExecuteAsync（一步完成）
                var result = await _dbAiService.GenerateAndExecuteAsync(
                    NaturalQuery,
                    "admin",
                    "administrator"
                );

                if (!result.Success)
                {
                    _dialogBox.ShowDialog("错误", $"操作失败：{result.Error}", DialogIconEnum.Error);
                    return;
                }

                _dialogBox.ShowDialog("成功",
                    $"操作成功，影响 {result.AffectedRows} 行",
                    DialogIconEnum.Info);
            }
            catch (Exception ex)
            {
                _dialogBox.ShowDialog("错误", $"操作失败：{ex.Message}", DialogIconEnum.Error);
            }
        }

                // UPDATE/INSERT/DELETE操作需要用户确认
                if (response.RequireConfirmation)
                {
                    var message = $"将执行以下操作：\n\n" +
                                $"SQL: {response.Sql}\n" +
                                $"类型: {response.SqlType}\n" +
                                $"影响表: {string.Join(", ", response.AffectedTables)}\n" +
                                $"预估行数: {response.EstimatedRows}\n" +
                                $"风险: {response.RiskLevel}\n" +
                                $"说明: {response.Explanation}";

                    if (!_dialogBox.ShowDialog("危险操作确认", message, DialogIconEnum.Warning))
                    {
                        return;
                    }
                }

                // 执行SQL
                using var context = App.ServiceProvider.GetRequiredService<ApplicationDbContext>();
                var result = await context.Database.ExecuteSqlRawAsync(response.Sql);

                _dialogBox.ShowDialog("成功", $"操作完成，影响 {result} 行", DialogIconEnum.Info);
            }
            catch (Exception ex)
            {
                _dialogBox.ShowDialog("错误", $"操作失败：{ex.Message}", DialogIconEnum.Error);
            }
        }
    }
}
```

## 典型使用场景

### 1. 用户管理界面

```csharp
// 场景1：查询所有激活用户
var query = "查询所有状态为激活的用户";
var response = await _dbAiService.GenerateSqlAsync(query);
// 生成：SELECT id, username, nickname, email, status FROM users WHERE status='active'

// 场景2：批量更新用户状态
var updateQuery = "将所有未激活超过30天的用户状态改为inactive";
var response = await _dbAiService.GenerateSqlAsync(updateQuery);
// 生成：UPDATE users SET status='inactive' WHERE status='pending' AND created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
```

### 2. 货架管理界面

```csharp
// 场景1：查询可用货架
var query = "查询所有状态为可用的货架及其槽位占用情况";
var response = await _dbAiService.GenerateSqlAsync(query);

// 场景2：批量修改货架配置
var updateQuery = "将E-Rack-1至E-Rack-10的货架，将它们的层数修改为5，槽数修改为6";
var response = await _dbAiService.GenerateSqlAsync(updateQuery);
```

### 3. 库存管理界面

```csharp
// 场景1：查询库存不足产品
var query = "查询库存低于最低库存预警值的产品，按缺货数量排序";
var response = await _dbAiService.GenerateSqlAsync(query);

// 场景2：查询库存变动记录
var query = "查询最近7天的所有库存变动记录";
var response = await _dbAiService.GenerateSqlAsync(query);
```

## 安全建议

1. **始终验证SQL**：在执行前调用验证接口
2. **高风险操作必须确认**：UPDATE/DELETE操作强制用户确认
3. **限制用户权限**：根据用户角色限制可执行的SQL类型
4. **记录操作日志**：记录所有通过AI生成的SQL操作
5. **定期审计**：检查AI生成的SQL是否符合业务规则

## 性能优化

1. **缓存常用SQL**：对于重复查询，缓存生成的SQL
2. **批量操作**：使用批量INSERT而不是单条INSERT
3. **索引优化**：根据AI建议添加必要的索引
4. **LIMIT限制**：SELECT查询始终添加LIMIT限制

## 故障排查

### 常见问题

1. **Ollama连接失败**
   - 检查Ollama服务是否启动：`ollama serve`
   - 确认配置文件中的URL正确

2. **SQL生成不准确**
   - 完善database_schema.json中的表结构描述
   - 添加详细的字段说明
   - 检查prompts.json中的示例是否覆盖业务场景

3. **响应速度慢**
   - 检查Ollama模型大小，考虑使用更小的模型
   - 增加Ollama的num_ctx参数（上下文长度）
   - 检查网络连接

## 最佳实践

1. **渐进式集成**：先在非核心功能中测试，再逐步扩展
2. **人工审核**：初期对AI生成的SQL进行人工审核
3. **持续优化**：根据使用反馈持续优化提示词和Schema配置
4. **版本控制**：将配置文件纳入版本控制
5. **文档记录**：记录常见查询及其对应的SQL，形成知识库

## 完整示例项目

参见 `examples/CSharpWpfExample/` 目录下的完整示例项目。
