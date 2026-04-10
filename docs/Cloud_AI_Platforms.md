# 云端AI平台配置指南

db-ai-server 支持多种云端AI平台，包括 Deep Seek、通义千问、智谱AI、OpenAI 和 Claude。

## 支持的平台

| 平台 | 显示名称 | 推荐模型 | API获取地址 |
|------|----------|----------|-------------|
| `deepseek` | Deep Seek | deepseek-coder | https://platform.deepseek.com |
| `qwen` | 通义千问 (阿里云百炼) | qwen-plus, qwen-coder-plus | https://bailian.console.aliyun.com |
| `zhipu` | 智谱AI (GLM) | glm-4-flash, glm-4 | https://open.bigmodel.cn |
| `openai` | OpenAI (ChatGPT) | gpt-4o-mini, gpt-4o | https://platform.openai.com |
| `claude` | Anthropic (Claude) | claude-3-5-haiku, claude-3-5-sonnet | https://console.anthropic.com |

## 快速配置

### 1. 获取API Key

访问各平台官网注册并获取API Key：

- **Deep Seek**: https://platform.deepseek.com → API Keys
- **通义千问**: https://bailian.console.aliyun.com → API-KEY
- **智谱AI**: https://open.bigmodel.cn → API Keys
- **OpenAI**: https://platform.openai.com → API Keys
- **Claude**: https://console.anthropic.com → API Keys

### 2. 修改配置

编辑 `config/server_config.json`：

```json
{
  "inference_engine": {
    "type": "deepseek",
    "api_key": "你的API Key",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-coder",
    "timeout": 120,
    "max_retries": 3,
    "temperature": 0.1,
    "max_tokens": 2048
  }
}
```

### 3. 切换平台

只需修改 `inference_engine.type` 字段即可切换不同平台：

| type值 | 平台 | 默认模型 |
|--------|------|----------|
| `deepseek` | Deep Seek | deepseek-chat |
| `qwen` | 通义千问 | qwen-plus |
| `zhipu` | 智谱AI | glm-4-flash |
| `openai` | OpenAI | gpt-4o-mini |
| `claude` | Claude | claude-3-5-haiku-20241022 |

## 各平台详细配置

### Deep Seek

**特点**: 国产大模型，代码能力强，价格实惠

**推荐模型**:
- `deepseek-coder` - 代码专用，推荐用于SQL生成
- `deepseek-chat` - 通用对话

```json
{
  "type": "deepseek",
  "api_key": "your-deepseek-api-key",
  "base_url": "https://api.deepseek.com/v1",
  "model": "deepseek-coder"
}
```

### 通义千问 (阿里云百炼)

**特点**: 阿里云大模型，中文能力强

**推荐模型**:
- `qwen-coder-plus` - 代码专用
- `qwen-plus` - 通用高性能
- `qwen-turbo` - 快速响应
- `qwen-max` - 最强能力

```json
{
  "type": "qwen",
  "api_key": "your-aliyun-api-key",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "model": "qwen-coder-plus"
}
```

### 智谱AI (GLM)

**特点**: 智谱AI出品，中英文兼顾

**推荐模型**:
- `glm-4-flash` - 快速免费
- `glm-4` - 高性能
- `glm-4-plus` - 最强能力

```json
{
  "type": "zhipu",
  "api_key": "your-zhipu-api-key",
  "base_url": "https://open.bigmodel.cn/api/paas/v4",
  "model": "glm-4-flash"
}
```

### OpenAI (ChatGPT)

**特点**: 国际领先模型，通用能力强

**推荐模型**:
- `gpt-4o-mini` - 高性价比
- `gpt-4o` - 最强能力
- `gpt-4-turbo` - 平衡之选

```json
{
  "type": "openai",
  "api_key": "your-openai-api-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o-mini"
}
```

### Claude (Anthropic)

**特点**: Anthropic大模型，分析能力强

**推荐模型**:
- `claude-3-5-haiku-20241022` - 快速响应
- `claude-3-5-sonnet-20241022` - 高性能

```json
{
  "type": "claude",
  "api_key": "your-anthropic-api-key",
  "base_url": "https://api.anthropic.com/v1",
  "model": "claude-3-5-haiku-20241022"
}
```

## 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `type` | 平台类型 | - |
| `api_key` | API密钥（必填） | - |
| `base_url` | API地址 | 平台默认值 |
| `model` | 模型名称 | 平台默认 |
| `timeout` | 请求超时（秒） | 120 |
| `max_retries` | 最大重试次数 | 3 |
| `temperature` | 温度参数（0-1） | 0.1 |
| `max_tokens` | 最大生成长度 | 2048 |

## 与本地模型对比

| 特性 | 云端AI平台 | 本地模型 (Ollama/LM Studio) |
|------|-----------|----------------------------|
| 成本 | 按量付费/订阅 | 免费（本地运行） |
| 性能 | 强大（云端算力） | 依赖本地硬件 |
| 隐私 | 数据需上传 | 完全本地 |
| 网络 | 需要网络连接 | 离线可用 |
| 配置 | 简单（只需API Key） | 需安装配置模型 |
| 推荐场景 | 生产环境、高质量需求 | 开发测试、数据敏感 |

## 故障排除

### 问题: "Missing API key"

**原因**: 未配置API Key

**解决方法**: 在 `server_config.json` 中添加 `api_key` 字段

### 问题: "Connection timeout"

**原因**: 网络问题或API服务不可用

**解决方法**:
1. 检查网络连接
2. 增加 `timeout` 值
3. 检查API Key是否有效

### 问题: "Rate limit exceeded"

**原因**: 请求频率超出限制

**解决方法**: 
1. 降低请求频率
2. 升级API套餐
3. 切换到其他平台
