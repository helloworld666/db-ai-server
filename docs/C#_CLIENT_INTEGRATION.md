# C#/.NET 集成指南 - DB-AI-Server v5.0

## 📖 概述

本文档说明如何在 C#/.NET 项目中集成 DB-AI-Server，实现通过自然语言生成SQL语句。

**技术栈**：简化架构，直接SQL生成

## 🎯 核心特性

### 简化架构 v5.0
- **直接SQL生成**：无需复杂的ReAct循环
- **纯SQL返回**：LLM直接返回可执行的SQL语句
- **无工具调用循环**：避免ToolMessage大JSON问题
- **快速响应**：减少LLM调用次数

### 开发效率
- **自然语言转SQL**：输入描述，直接获得SQL
- **Schema感知**：自动获取数据库结构
- **安全验证**：SQL执行前自动验证

## 📡 API端点

### 1. 生成SQL (主要入口)

**端点**: `POST /mcp/generate_sql`

**请求格式**:
```json
{
  "query": "查询所有用户"
}
```

**响应格式**:
```json
{
  "success": true,
  "sql": "SELECT * FROM users"
}
```

**失败响应**:
```json
{
  "success": false,
  "error": "未能生成SQL语句",
  "raw_response": "..."
}
```

### 2. 执行SQL

**端点**: `POST /mcp/execute_sql`

**请求格式**:
```json
{
  "sql": "SELECT * FROM users"
}
```

**响应格式**:
```json
{
  "success": true,
  "rows": [
    {"id": 1, "name": "admin"},
    {"id": 2, "name": "user"}
  ],
  "row_count": 2,
  "columns": ["id", "name"]
}
```

### 3. 获取数据库结构

**端点**: `GET /mcp/get_schema`

**响应格式**:
```json
{
  "database_name": "mydb",
  "tables": [
    {
      "name": "users",
      "description": "用户表",
      "columns": [
        {"name": "id", "type": "int", "primary_key": true},
        {"name": "name", "type": "varchar"}
      ]
    }
  ]
}
```

## 💻 C#客户端示例

### 完整调用示例

```csharp
using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

public class DbAiClient
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;
    
    public DbAiClient(string baseUrl)
    {
        _baseUrl = baseUrl;
        _httpClient = new HttpClient();
    }
    
    /// <summary>
    /// 生成SQL语句
    /// </summary>
    public async Task<string> GenerateSqlAsync(string query)
    {
        var request = new { query = query };
        var json = JsonSerializer.Serialize(request);
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        
        var response = await _httpClient.PostAsync($"{_baseUrl}/mcp/generate_sql", content);
        response.EnsureSuccessStatusCode();
        
        var responseJson = await response.Content.ReadAsStringAsync();
        var result = JsonSerializer.Deserialize<JsonElement>(responseJson);
        
        if (result.GetProperty("success").GetBoolean())
        {
            return result.GetProperty("sql").GetString();
        }
        
        throw new Exception($"生成SQL失败: {result.GetProperty("error").GetString()}");
    }
    
    /// <summary>
    /// 执行SQL语句
    /// </summary>
    public async Task<JsonElement> ExecuteSqlAsync(string sql)
    {
        var request = new { sql = sql };
        var json = JsonSerializer.Serialize(request);
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        
        var response = await _httpClient.PostAsync($"{_baseUrl}/mcp/execute_sql", content);
        response.EnsureSuccessStatusCode();
        
        var responseJson = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<JsonElement>(responseJson);
    }
    
    /// <summary>
    /// 自然语言查询（生成并执行SQL）
    /// </summary>
    public async Task<JsonElement> QueryAsync(string naturalLanguageQuery)
    {
        // 步骤1: 生成SQL
        var sql = await GenerateSqlAsync(naturalLanguageQuery);
        Console.WriteLine($"生成的SQL: {sql}");
        
        // 步骤2: 执行SQL
        return await ExecuteSqlAsync(sql);
    }
}

// 使用示例
public class Program
{
    public static async Task Main()
    {
        var client = new DbAiClient("http://localhost:8080");
        
        try
        {
            // 示例1: 查询所有用户
            var result1 = await client.QueryAsync("查询所有用户");
            Console.WriteLine($"结果: {result1}");
            
            // 示例2: 只生成SQL不执行
            var sql = await client.GenerateSqlAsync("查询最近10条日志");
            Console.WriteLine($"生成的SQL: {sql}");
            
            // 示例3: 执行自定义SQL
            var result3 = await client.ExecuteSqlAsync("SELECT COUNT(*) as total FROM users");
            Console.WriteLine($"用户总数: {result3}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"错误: {ex.Message}");
        }
    }
}
```

## 🔧 配置说明

### 配置文件: `config/prompts.json`

```json
{
  "system_prompt": "你是一个SQL生成助手...",
  "instructions": {
    "core_rules": [
      "只能使用数据库中真实存在的表名和字段名",
      "禁止编造 schema 中不存在的字段名",
      "DELETE/UPDATE 必须有 WHERE 条件"
    ]
  }
}
```

### 数据库配置

在 `.env` 或环境变量中配置:

```
DATABASE_URL=mysql://user:password@localhost:3306/dbname
LLM_PROVIDER=openai
LLM_MODEL=gpt-3.5-turbo
LLM_API_KEY=your-api-key
```

## ⚠️ 注意事项

1. **SQL验证**: 所有生成的SQL在执行前都会经过安全验证
2. **Schema缓存**: 数据库结构会缓存，如表结构变更请重启服务
3. **超时设置**: 生成SQL默认超时60秒，执行SQL默认超时30秒

## 📚 版本历史

- **v5.0** (当前): 简化架构，移除ReAct循环，直接SQL生成
- **v4.x**: 基于LangChain ReAct的Agent架构（已废弃）
