"""数据库Schema管理器 - 从配置文件动态加载

所有Schema信息必须从配置文件读取，禁止硬编码
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class SchemaManager:
    """数据库Schema管理器"""

    def __init__(self, config_path: str = "config"):
        """
        初始化Schema管理器

        Args:
            config_path: 配置文件目录路径
        """
        self.config_path = Path(config_path)
        self._schema_cache: Optional[Dict[str, Any]] = None
        self._table_cache: Dict[str, Dict[str, Any]] = {}
        self._load_schema()

    def _load_schema(self):
        """从配置文件加载Schema"""
        schema_file = self.config_path / "database_schema.json"
        if schema_file.exists():
            with open(schema_file, "r", encoding="utf-8") as f:
                self._schema_cache = json.load(f)
            logger.info(f"已加载Schema，包含 {len(self.get_all_table_names())} 个表")
        else:
            self._schema_cache = {"tables": []}
            logger.warning(f"Schema配置文件不存在: {schema_file}")

    def reload(self):
        """重新加载Schema"""
        self._schema_cache = None
        self._table_cache = {}
        self._load_schema()

    def get_full_schema(self) -> Dict[str, Any]:
        """获取完整Schema"""
        if self._schema_cache is None:
            self._load_schema()
        return self._schema_cache

    def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """获取指定表的Schema"""
        if table_name in self._table_cache:
            return self._table_cache[table_name]

        schema = self.get_full_schema()
        for table in schema.get('tables', []):
            if table['name'].lower() == table_name.lower():
                self._table_cache[table_name] = table
                return table
        return None

    def get_all_table_names(self) -> List[str]:
        """获取所有表名"""
        schema = self.get_full_schema()
        return [table['name'] for table in schema.get('tables', [])]

    def get_column_names(self, table_name: str) -> List[str]:
        """获取指定表的所有列名"""
        table_schema = self.get_table_schema(table_name)
        if table_schema:
            return [col['name'] for col in table_schema.get('columns', [])]
        return []

    def get_column_info(self, table_name: str, column_name: str) -> Optional[Dict[str, Any]]:
        """获取列详细信息"""
        table_schema = self.get_table_schema(table_name)
        if not table_schema:
            return None
        for column in table_schema.get('columns', []):
            if column['name'].lower() == column_name.lower():
                return column
        return None

    def format_schema_for_prompt(self) -> str:
        """格式化Schema为提示词友好的文本"""
        schema = self.get_full_schema()
        lines = []

        lines.append("## 数据库Schema")
        lines.append(f"数据库名称: {schema.get('database_name', 'unknown')}")
        lines.append(f"数据库类型: {schema.get('database_type', 'unknown')}")
        lines.append(f"描述: {schema.get('description', 'No description')}\n")

        for table in schema.get('tables', []):
            lines.append(f"### 表: {table['name']}")
            if 'description' in table:
                lines.append(f"描述: {table['description']}")

            lines.append("字段:")
            for column in table.get('columns', []):
                line = f"  - {column['name']} ({column['type']})"
                if column.get('primary_key'):
                    line += " [主键]"
                if column.get('required'):
                    line += " [必填]"
                if column.get('unique'):
                    line += " [唯一]"
                if 'description' in column:
                    line += f" - {column['description']}"
                lines.append(line)
            lines.append("")

        return "\n".join(lines)

    def get_table_summary(self) -> List[Dict[str, str]]:
        """获取表摘要（表名和描述）"""
        schema = self.get_full_schema()
        summary = []
        for table in schema.get('tables', []):
            summary.append({
                "table": table['name'],
                "description": table.get('description', '')
            })
        return summary

    def get_column_display_mapping(self, table_name: str, column_name: str) -> Optional[Dict[str, Any]]:
        """获取列的显示映射配置"""
        column_info = self.get_column_info(table_name, column_name)
        if not column_info:
            return None
        return {
            "display_mapping": column_info.get("display_mapping"),
            "output_name": column_info.get("output_name")
        }

    def get_table_display_mappings(self, table_name: str) -> Dict[str, Dict[str, Any]]:
        """获取表中所有需要显示映射的字段"""
        table_schema = self.get_table_schema(table_name)
        if not table_schema:
            return {}

        mappings = {}
        for column in table_schema.get("columns", []):
            if "display_mapping" in column:
                mappings[column["name"]] = {
                    "display_mapping": column["display_mapping"],
                    "output_name": column.get("output_name", column["name"])
                }
        return mappings
