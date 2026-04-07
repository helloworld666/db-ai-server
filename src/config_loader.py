"""
配置加载器 - 负责加载和管理所有配置文件
"""

import json
import logging
import os
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
            logger.warning(f"Config file not found: {file_path}, using empty config")
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
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
            key: 配置键，支持点号分隔的路径，如 'server.ollama.model'
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._cache
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            
            if value is None:
                return default
        
        return value
    
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


# 全局配置加载器实例
_config_loader: Optional[ConfigLoader] = None


def get_config_loader(config_dir: str = "config") -> ConfigLoader:
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
