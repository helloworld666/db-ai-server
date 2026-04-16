"""SQL验证器 - 从配置文件加载规则

所有安全规则必须从配置文件读取，禁止硬编码
"""
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SQLValidator:
    """SQL验证器 - 基于配置文件的验证规则"""

    def __init__(self, config_path: str = "config"):
        """
        初始化SQL验证器

        Args:
            config_path: 配置文件目录路径
        """
        self.config_path = Path(config_path)
        self._rules_cache: Optional[Dict[str, Any]] = None
        self._load_rules()

    def _load_rules(self):
        """从配置文件加载安全规则"""
        rules_file = self.config_path / "security_rules.json"
        if rules_file.exists():
            with open(rules_file, "r", encoding="utf-8") as f:
                self._rules_cache = json.load(f)
            logger.info("已加载安全规则配置")
        else:
            self._rules_cache = self._get_default_rules()
            logger.warning(f"安全规则配置文件不存在: {rules_file}，使用默认规则")

    def _get_default_rules(self) -> Dict[str, Any]:
        """获取默认规则"""
        return {
            "dangerous_keywords": ["DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE", "SHOW", "DESCRIBE"],
            "allowed_sql_types": ["SELECT", "UPDATE", "INSERT", "DELETE"],
            "forbidden_patterns": [
                {"pattern": ";\\s*\\w+", "description": "Keyword after semicolon", "severity": "critical"},
                {"pattern": "--.*$", "description": "SQL comment", "severity": "high"},
                {"pattern": "union\\s+select", "description": "UNION injection", "severity": "critical"},
                {"pattern": "\\bor\\s+\\d+\\s*=\\s*\\d+", "description": "OR injection", "severity": "high"},
            ]
        }

    def reload(self):
        """重新加载规则"""
        self._rules_cache = None
        self._load_rules()

    def validate(self, sql: str) -> Dict[str, Any]:
        """
        验证SQL语句

        Returns:
            验证结果字典
        """
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "sql_type": None
        }

        if not sql or not isinstance(sql, str):
            result["is_valid"] = False
            result["errors"].append("SQL语句为空或无效")
            return result

        sql_upper = sql.upper().strip()

        # 检查危险关键词
        dangerous_keywords = self._rules_cache.get("dangerous_keywords", [])
        for keyword in dangerous_keywords:
            if re.search(r'\b' + keyword + r'\b', sql_upper):
                result["is_valid"] = False
                result["errors"].append(f"禁止使用 {keyword} 关键词")

        if not result["is_valid"]:
            return result

        # 检查SQL类型
        allowed_types = self._rules_cache.get("allowed_sql_types", [])
        sql_type = sql_upper.split()[0] if sql_upper else ""
        if sql_type not in allowed_types:
            result["is_valid"] = False
            result["errors"].append(f"不支持的SQL类型: {sql_type}")
            return result

        result["sql_type"] = sql_type

        # DELETE必须包含WHERE
        if sql_type == "DELETE" and "WHERE" not in sql_upper:
            result["is_valid"] = False
            result["errors"].append("DELETE语句必须包含WHERE条件")
            return result

        # UPDATE建议包含WHERE
        if sql_type == "UPDATE" and "WHERE" not in sql_upper:
            result["warnings"].append("UPDATE语句建议包含WHERE条件")

        # SELECT优化建议
        if sql_type == "SELECT":
            if "SELECT *" in sql_upper:
                result["warnings"].append("建议明确指定查询字段，避免使用SELECT *")
            if "LIMIT" not in sql_upper:
                result["warnings"].append("建议添加LIMIT限制以避免返回过多数据")

        # 检查禁止的模式
        forbidden_patterns = self._rules_cache.get("forbidden_patterns", [])
        for pattern_info in forbidden_patterns:
            pattern = pattern_info.get("pattern", "")
            if re.search(pattern, sql_upper, re.IGNORECASE):
                severity = pattern_info.get("severity", "high")
                if severity == "critical":
                    result["is_valid"] = False
                    result["errors"].append(f"检测到安全威胁: {pattern_info.get('description', '未知')}")
                elif severity == "high":
                    result["warnings"].append(f"检测到可疑模式: {pattern_info.get('description', '未知')}")

        return result

    def check_injection(self, sql: str) -> bool:
        """检测SQL注入"""
        sql_upper = sql.upper()
        injection_patterns = [
            r';\s*(DROP|ALTER|DELETE|UPDATE|INSERT|CREATE|TRUNCATE)',
            r'--.*?(DROP|ALTER|DELETE|UPDATE|INSERT)',
            r'UNION\s+SELECT',
            r'\bOR\s+\d+\s*=\s*\d+',
            r'\bAND\s+\d+\s*=\s*\d+',
        ]
        for pattern in injection_patterns:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                logger.warning(f"检测到SQL注入模式: {pattern}")
                return True
        return False

    def evaluate_risk(self, sql: str, sql_type: str, estimated_rows: int = 1) -> str:
        """评估SQL风险等级"""
        sql_upper = sql.upper()
        if sql_type == "DELETE":
            return "high" if "WHERE" in sql_upper else "critical"
        if sql_type == "UPDATE":
            if estimated_rows > 100:
                return "high"
            if "WHERE" not in sql_upper:
                return "high"
            if estimated_rows > 10:
                return "medium"
            return "low"
        if sql_type == "INSERT":
            if estimated_rows > 10:
                return "medium"
            return "low"
        if sql_type == "SELECT":
            if estimated_rows > 1000:
                return "medium"
            return "low"
        return "medium"

    def generate_suggestions(self, sql: str, sql_type: str) -> List[str]:
        """生成SQL优化建议"""
        suggestions = []
        if not sql:
            return suggestions
        sql_upper = sql.upper()
        if sql_type == "SELECT":
            if "SELECT *" in sql_upper:
                suggestions.append("建议明确指定查询字段，避免使用SELECT *")
            if "LIMIT" not in sql_upper:
                suggestions.append("建议添加LIMIT限制")
        elif sql_type == "UPDATE":
            if "WHERE" not in sql_upper:
                suggestions.append("UPDATE缺少WHERE条件，将更新整表数据")
        elif sql_type == "DELETE":
            if "WHERE" not in sql_upper:
                suggestions.append("DELETE缺少WHERE条件，将删除整表数据")
        return suggestions
