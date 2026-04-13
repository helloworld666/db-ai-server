"""
配置加载器 - 负责加载和管理所有配置文件
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器类"""

    def __init__(self, config_dir: str = "config"):
        """
        初始化配置加载器

        Args:
            config_dir: 配置文件目录路径
        """
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, Any] = {}
        self._load_configs()

    def _load_configs(self):
        """加载所有配置文件"""
        logger.info(f"Loading configurations from: {self.config_dir}")

        # 加载服务器配置
        self._cache['server'] = self._load_json('server_config.json')

        # 加载数据库Schema
        self._cache['schema'] = self._load_json('database_schema.json')

        # 加载提示词配置
        self._cache['prompts'] = self._load_json('prompts.json')

        # 加载安全规则
        self._cache['security'] = self._load_json('security_rules.json')

        # 加载云端AI平台配置
        self._cache['cloud_platforms'] = self._load_json('cloud_platforms.json')

        logger.info("All configurations loaded successfully")

    def _load_json(self, filename: str) -> Dict[str, Any]:
        """
        加载JSON配置文件

        Args:
            filename: 文件名

        Returns:
            配置字典
        """
        file_path = self.config_dir / filename

        if not file_path.exists():
            logger.debug(f"Config file not found: {file_path}, using empty config")
            return {}

        try:
            # 使用 utf-8-sig 编码处理可能的 BOM (Byte Order Mark)
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                config = json.load(f)

            logger.debug(f"Loaded config from {filename}")
            return config

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {filename}: {e}")
            raise ValueError(f"Invalid JSON in {filename}: {e}")
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键，支持点号分隔的路径，如 'server.inference_engine.type'
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')

        # 首先尝试直接在 _cache 中查找（支持顶级键，如 'inference_engine.type'）
        if len(keys) >= 1:
            first_key = keys[0]
            # 在所有缓存的配置字典中查找第一个键
            for config_name, config_value in self._cache.items():
                if isinstance(config_value, dict) and first_key in config_value:
                    value = config_value
                    # 继续遍历剩余的键
                    for k in keys:
                        if isinstance(value, dict):
                            value = value.get(k)
                        else:
                            value = None
                            break
                        if value is None:
                            break
                    if value is not None:
                        return value

        # 旧方法：在 _cache 中查找（支持 'server.ollama.model' 这样的路径）
        value = self._cache
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                break
            if value is None:
                break

        if value is not None:
            return value

        return default

    def get_inference_config(self) -> Dict[str, Any]:
        """
        获取推理引擎配置（统一配置）

        Returns:
            推理引擎配置字典
        """
        return self.get('inference_engine', {})

    def reload(self):
        """重新加载所有配置"""
        logger.info("Reloading all configurations...")
        self._cache.clear()
        self._load_configs()

    def get_server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return self._cache.get('server', {})

    def get_database_schema(self) -> Dict[str, Any]:
        """获取数据库Schema配置"""
        return self._cache.get('schema', {})

    def get_prompts_config(self) -> Dict[str, Any]:
        """获取提示词配置"""
        return self._cache.get('prompts', {})

    def get_security_rules(self) -> Dict[str, Any]:
        """获取安全规则配置"""
        return self._cache.get('security', {})

    def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定表的Schema

        Args:
            table_name: 表名

        Returns:
            表Schema字典，如果不存在返回None
        """
        schema = self.get_database_schema()

        for table in schema.get('tables', []):
            if table['name'].lower() == table_name.lower():
                return table

        return None

    def get_all_table_names(self) -> list[str]:
        """获取所有表名"""
        schema = self.get_database_schema()
        return [table['name'] for table in schema.get('tables', [])]

    def get_ollama_config(self) -> Dict[str, Any]:
        """获取Ollama配置"""
        return self.get('server.ollama', {})

    def get_security_config(self) -> Dict[str, Any]:
        """获取安全配置"""
        return self.get('server.security', {})

    def get_cloud_platform_config(self, platform: str) -> Dict[str, Any]:
        """
        获取指定云端AI平台的配置

        Args:
            platform: 平台类型 (deepseek, qwen, zhipu, openai, claude)

        Returns:
            云端平台配置字典
        """
        cloud_platforms = self._cache.get('cloud_platforms', {})
        return cloud_platforms.get(platform, {})

    def get_all_cloud_platforms(self) -> Dict[str, Any]:
        """
        获取所有云端AI平台配置

        Returns:
            所有云端平台配置字典
        """
        return self._cache.get('cloud_platforms', {})




# 全局配置加载器实例
_config_loader: Optional[ConfigLoader] = None


def get_config_loader(config_dir: str = "config") -> ConfigLoader | None:
    """
    获取全局配置加载器实例（单例模式）

    Args:
        config_dir: 配置目录路径

    Returns:
        ConfigLoader实例
    """
    global _config_loader

    if _config_loader is None:
        _config_loader = ConfigLoader(config_dir)

    return _config_loader
