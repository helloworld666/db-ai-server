"""配置模型 - Pydantic V2

使用Pydantic V2进行配置验证和类型管理
所有配置从JSON文件动态加载
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM配置模型"""
    provider: str = Field(default="openai", description="LLM提供商")
    model: str = Field(default="gpt-4o-mini", description="模型名称")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    base_url: Optional[str] = Field(default=None, description="API基础URL")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=2048, ge=1, description="最大生成长度")
    timeout: int = Field(default=120, ge=1, description="超时时间(秒)")
    max_retries: int = Field(default=3, ge=0, description="最大重试次数")

    def get_model_id(self) -> str:
        """获取LangChain标准模型标识符"""
        provider_map = {
            "openai": "openai",
            "anthropic": "anthropic",
            "claude": "anthropic",
            "deepseek": "openai",
            "qwen": "openai",
            "ollama": "ollama",
            "lmstudio": "openai",
            "openrouter": "openai",
        }
        langchain_provider = provider_map.get(self.provider.lower(), self.provider.lower())
        return f"{langchain_provider}:{self.model}"


class DatabaseConfig(BaseModel):
    """数据库配置模型"""
    connection_string: Optional[str] = Field(default=None, description="数据库连接字符串")
    enable_direct_query: bool = Field(default=True, description="是否启用直接查询")


class SecurityConfig(BaseModel):
    """安全配置模型"""
    allowed_ips: List[str] = Field(default_factory=lambda: ["127.0.0.1", "::1"])
    enable_rate_limit: bool = Field(default=True)
    max_requests_per_minute: int = Field(default=60)


class ServerConfig(BaseModel):
    """服务器配置模型"""
    name: str = Field(default="db-ai-server")
    version: str = Field(default="7.0.0")
    description: str = Field(default="AI-powered database SQL generation server")


class Settings(BaseModel):
    """全局设置模型"""
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    config_dir: Path = Field(default=Path("config"))

    model_config = {"extra": "ignore"}

    @classmethod
    def from_json_files(cls, config_dir: str = "config") -> "Settings":
        """从JSON配置文件加载设置"""
        config_path = Path(config_dir)
        server_config_path = config_path / "server_config.json"

        if not server_config_path.exists():
            return cls()

        with open(server_config_path, "r", encoding="utf-8") as f:
            raw_config = json.load(f)

        server_cfg = raw_config.get("server", {})
        database_cfg = raw_config.get("database", {})
        inference_cfg = raw_config.get("inference_engine", {})
        security_cfg = raw_config.get("security", {})

        return cls(
            server=ServerConfig(**server_cfg),
            database=DatabaseConfig(**database_cfg),
            llm=LLMConfig(
                provider=inference_cfg.get("type", "openai"),
                model=inference_cfg.get("model", "gpt-4o-mini"),
                api_key=inference_cfg.get("api_key"),
                base_url=inference_cfg.get("base_url"),
                temperature=inference_cfg.get("temperature", 0.7),
                max_tokens=inference_cfg.get("max_tokens", 2048),
                timeout=inference_cfg.get("timeout", 120),
                max_retries=inference_cfg.get("max_retries", 3),
            ),
            security=SecurityConfig(**security_cfg),
            config_dir=config_path,
        )


# 全局设置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取全局设置实例（单例模式）"""
    global _settings
    if _settings is None:
        _settings = Settings.from_json_files()
    return _settings


def reload_settings(config_dir: str = "config") -> Settings:
    """重新加载设置"""
    global _settings
    _settings = Settings.from_json_files(config_dir)
    return _settings
