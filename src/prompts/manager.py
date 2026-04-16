"""提示词管理器 - 从配置文件动态加载

所有提示词必须从配置文件读取，禁止硬编码
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PromptManager:
    """提示词管理器 - 所有提示词从配置文件读取"""

    def __init__(self, config_path: str = "config"):
        """
        初始化提示词管理器

        Args:
            config_path: 配置文件目录路径
        """
        self.config_path = Path(config_path)
        self._prompts_cache: Optional[Dict[str, Any]] = None
        self._load_prompts()

    def _load_prompts(self):
        """从配置文件加载提示词"""
        prompts_file = self.config_path / "prompts.json"
        if prompts_file.exists():
            with open(prompts_file, "r", encoding="utf-8") as f:
                self._prompts_cache = json.load(f)
            logger.info("已加载提示词配置")
        else:
            self._prompts_cache = {}
            logger.warning(f"提示词配置文件不存在: {prompts_file}")

    def reload(self):
        """重新加载提示词"""
        self._prompts_cache = None
        self._load_prompts()

    def get_agent_system_prompt(self) -> str:
        """获取Agent系统提示词"""
        agent_config = self._prompts_cache.get("agent", {})
        return agent_config.get("system_prompt", "")

    def get_agent_max_iterations(self) -> int:
        """获取Agent最大迭代次数"""
        agent_config = self._prompts_cache.get("agent", {})
        return agent_config.get("max_iterations", 10)

    def get_sql_generation_system_prompt(self) -> str:
        """获取SQL生成的系统提示词"""
        sql_gen_config = self._prompts_cache.get("sql_generation", {})
        return sql_gen_config.get("system_prompt", "")

    def get_sql_generation_rules(self) -> list:
        """获取SQL生成规则"""
        sql_gen_config = self._prompts_cache.get("sql_generation", {})
        return sql_gen_config.get("rules", [])

    def get_instructions(self) -> Dict[str, Any]:
        """获取指令配置"""
        return self._prompts_cache.get("instructions", {})

    def get_core_rules(self) -> list:
        """获取核心规则"""
        return self.get_instructions().get("core_rules", [])

    def get_output_constraints(self) -> list:
        """获取输出约束"""
        return self.get_instructions().get("output_constraints", [])

    def get_business_rules(self) -> Dict[str, str]:
        """获取业务规则"""
        return self._prompts_cache.get("business_rules", {})

    def get_examples(self) -> list:
        """获取示例"""
        return self._prompts_cache.get("examples", [])
