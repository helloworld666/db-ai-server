"""配置加载器 - 从JSON文件动态加载配置

所有配置必须从配置文件读取，禁止硬编码
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器 - 统一管理所有JSON配置文件的加载"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, Any] = {}

    def load_json(self, filename: str) -> Dict[str, Any]:
        """
        加载JSON配置文件

        Args:
            filename: 配置文件名（如 server_config.json）

        Returns:
            配置字典
        """
        if filename in self._cache:
            return self._cache[filename]

        config_path = self.config_dir / filename
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cache[filename] = data
                logger.info(f"已加载配置文件: {filename}")
                return data
        except json.JSONDecodeError as e:
            logger.error(f"配置文件解析失败 {filename}: {e}")
            return {}

    def reload(self, filename: Optional[str] = None):
        """重新加载配置"""
        if filename:
            self._cache.pop(filename, None)
        else:
            self._cache.clear()

    def load_server_config(self) -> Dict[str, Any]:
        """加载服务器配置"""
        return self.load_json("server_config.json")

    def load_prompts(self) -> Dict[str, Any]:
        """加载提示词配置"""
        return self.load_json("prompts.json")

    def load_schema(self) -> Dict[str, Any]:
        """加载数据库Schema配置"""
        return self.load_json("database_schema.json")

    def load_security_rules(self) -> Dict[str, Any]:
        """加载安全规则配置"""
        return self.load_json("security_rules.json")

    def load_cloud_platforms(self) -> Dict[str, Any]:
        """加载云平台配置"""
        return self.load_json("cloud_platforms.json")
