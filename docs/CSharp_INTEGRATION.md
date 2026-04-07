# C# 集成指南

本文档说明如何在C#/.NET项目中集成db-ai-server MCP Server。

## 📋 前置要求

- .NET 6.0 或更高版本
- db-ai-server MCP Server 已安装并运行
- Ollama 服务正在运行

## 🚀 快速集成

### 1. 添加NuGet包

```bash
dotnet add package System.Text.Json
dotnet add package System.Net.Http.Json
```

### 2. 创建MCP客户端类

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

public class SqlGenerationArguments
{
    [JsonPropertyName("query")]
    public string Query { get; set; } = string.Empty;

    [JsonPropertyName("user_context")]
    public UserContext? UserContext { get; set; }
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

public class UserContext
{
    [JsonPropertyName("username")]
    public string? Username { get; set; }

    [JsonPropertyName("role")]
    public string? Role { get; set; }

    [JsonPropertyName("permissions")]
    public List<string>? Permissions { get; set; }
}

public class SqlGenerationResponse
{
    [JsonPropertyName("sql")]
    public string Sql { get; set; } = string.Empty;

    [JsonPropertyName("sql_type")]
    public string SqlType { get; set; } = string.Empty;

    [JsonPropertyName("affected_tables")]
    public List<string> AffectedTables { get; set; } = new();

    [JsonPropertyName("estimated_rows")]
    public int EstimatedRows { get; set; }

    [JsonPropertyName("risk_level")]
    public string RiskLevel { get; set; } = string.Empty;

    [JsonPropertyName("explanation")]
    public string Explanation { get; set; } = string.Empty;

    [JsonPropertyName("require_confirmation")]
    public bool RequireConfirmation { get; set; }

    [JsonPropertyName("warnings")]
    public List<string> Warnings { get; set; } = new();

    [JsonPropertyName("validation")]
    public ValidationResult? Validation { get; set; }
}

public class ValidationResult
{
    [JsonPropertyName("is_valid")]
    public bool IsValid { get; set; }

    [JsonPropertyName("errors")]
    public List<string> Errors { get; set; } = new();

    [JsonPropertyName("warnings")]
    public List<string> Warnings { get; set; } = new();
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

### 3. 在WPF中使用

```csharp
public class AiUpdateViewModel
{
    private readonly McpClient _mcpClient;

    public AiUpdateViewModel()
    {
        _mcpClient = new McpClient("http://localhost:8080");
    }

    public async Task GenerateSqlAsync()
    {
        try
        {
            var response = await _mcpClient.GenerateSqlAsync(
                "修改所有状态为inactive的用户为active状态",
                new UserContext
                {
                    Username = "admin",
                    Role = "administrator",
                    Permissions = new List<string> { "sql:execute", "users:update" }
                });

            if (response.Validation != null && !response.Validation.IsValid)
            {
                // SQL验证失败
                MessageBox.Show(
                    $"SQL验证失败:\n{string.Join("\n", response.Validation.Errors)}",
                    "错误",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);
                return;
            }

            // 显示生成的SQL
            string message = $"""
                生成的SQL:
                {response.Sql}

                类型: {response.SqlType}
                影响表: {string.Join(", ", response.AffectedTables)}
                预估行数: {response.EstimatedRows}
                风险等级: {response.RiskLevel}
                说明: {response.Explanation}
                """;

            if (response.RequireConfirmation)
            {
                var result = MessageBox.Show(
                    message + "\n\n是否确认执行？",
                    "确认",
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Warning);

                if (result == MessageBoxResult.Yes)
                {
                    await ExecuteSqlAsync(response.Sql);
                }
            }
            else
            {
                MessageBox.Show(message, "SQL生成成功", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"生成SQL失败: {ex.Message}",
                "错误",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
    }

    private async Task ExecuteSqlAsync(string sql)
    {
        // 在这里执行SQL到您的数据库
        // 例如使用Entity Framework Core
        
        await using var context = new ApplicationDbContext();
        var affectedRows = await context.Database.ExecuteSqlRawAsync(sql);
        
        MessageBox.Show(
            $"SQL执行成功，影响 {affectedRows} 行",
            "成功",
            MessageBoxButton.OK,
            MessageBoxImage.Information);
    }
}
```

## 🔧 高级用法

### 错误处理

```csharp
public async Task SafeGenerateSqlAsync(string query)
{
    try
    {
        // 检查服务器状态
        var status = await _mcpClient.GetServerStatusAsync();
        if (!status.Ollama.Connected)
        {
            throw new InvalidOperationException("Ollama未连接");
        }

        // 生成SQL
        var response = await _mcpClient.GenerateSqlAsync(query);

        // 验证响应
        if (response == null)
        {
            throw new InvalidOperationException("未能解析AI响应");
        }

        // 检查SQL验证结果
        if (response.Validation != null && !response.Validation.IsValid)
        {
            throw new InvalidOperationException(
                $"SQL验证失败: {string.Join(", ", response.Validation.Errors)}");
        }

        // 检查风险等级
        if (response.RiskLevel == "critical")
        {
            throw new InvalidOperationException("操作风险过高，已拒绝执行");
        }

        return response;
    }
    catch (HttpRequestException ex)
    {
        throw new InvalidOperationException($"无法连接到MCP Server: {ex.Message}", ex);
    }
    catch (JsonException ex)
    {
        throw new InvalidOperationException($"解析响应失败: {ex.Message}", ex);
    }
}
```

### 批量处理

```csharp
public async Task BatchGenerateSqlAsync(List<string> queries)
{
    var tasks = queries.Select(q => _mcpClient.GenerateSqlAsync(q));
    var results = await Task.WhenAll(tasks);

    foreach (var result in results)
    {
        Console.WriteLine($"SQL: {result.Sql}");
        Console.WriteLine($"Risk: {result.RiskLevel}");
        Console.WriteLine("---");
    }
}
```

### 日志记录

```csharp
public class LoggingMcpClient : McpClient
{
    private readonly ILogger<LoggingMcpClient> _logger;

    public LoggingMcpClient(
        string serverUrl,
        ILogger<LoggingMcpClient> logger) : base(serverUrl)
    {
        _logger = logger;
    }

    public async Task<SqlGenerationResponse> GenerateSqlAsync(
        string query,
        UserContext? userContext = null)
    {
        _logger.LogInformation("Generating SQL for query: {Query}", query);

        var response = await base.GenerateSqlAsync(query, userContext);

        _logger.LogInformation(
            "Generated SQL: {SqlType} on {Tables}, Risk: {Risk}",
            response.SqlType,
            string.Join(", ", response.AffectedTables),
            response.RiskLevel);

        return response;
    }
}
```

## 📚 完整示例

参见项目根目录的 `examples/csharp/` 目录，包含完整的WPF应用程序示例。

## 🔗 相关资源

- [MCP协议文档](https://modelcontextprotocol.io)
- [Ollama文档](https://ollama.com/docs)
- [.NET HTTP客户端](https://learn.microsoft.com/en-us/dotnet/fundamentals/networking/http/httpclient)
