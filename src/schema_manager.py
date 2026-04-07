"""
Schema管理器 - 管理数据库Schema信息
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class SchemaManager:
    """数据库Schema管理器"""
    
    def __init__(self, config_loader):
        """
        初始化Schema管理器
        
        Args:
            config_loader: 配置加载器实例
        """
        self.config_loader = config_loader
        self._schema_cache: Optional[Dict[str, Any]] = None
        self._table_cache: Dict[str, Dict[str, Any]] = {}
    
    async def get_full_schema(self) -> Dict[str, Any]:
        """
        获取完整数据库Schema
        
        Returns:
            完整Schema字典
        """
        if self._schema_cache is None:
            self._schema_cache = self.config_loader.get_database_schema()
            logger.debug(f"Loaded full schema with {len(self._schema_cache.get('tables', []))} tables")
        
        return self._schema_cache
    
    async def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定表的Schema
        
        Args:
            table_name: 表名
        
        Returns:
            表Schema字典，如果不存在返回None
        """
        # 检查缓存
        if table_name in self._table_cache:
            return self._table_cache[table_name]
        
        # 从完整Schema中查找
        schema = await self.get_full_schema()
        
        for table in schema.get('tables', []):
            if table['name'].lower() == table_name.lower():
                self._table_cache[table_name] = table
                return table
        
        logger.warning(f"Table '{table_name}' not found in schema")
        return None
    
    def get_all_table_names(self) -> List[str]:
        """
        获取所有表名
        
        Returns:
            表名列表
        """
        schema = self.config_loader.get_database_schema()
        return [table['name'] for table in schema.get('tables', [])]
    
    def get_column_names(self, table_name: str) -> List[str]:
        """
        获取指定表的所有列名
        
        Args:
            table_name: 表名
        
        Returns:
            列名列表
        """
        table_schema = self.config_loader.get_table_schema(table_name)
        
        if table_schema:
            return [col['name'] for col in table_schema.get('columns', [])]
        
        return []
    
    def get_column_info(self, table_name: str, column_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定列的详细信息
        
        Args:
            table_name: 表名
            column_name: 列名
        
        Returns:
            列信息字典，如果不存在返回None
        """
        table_schema = self.config_loader.get_table_schema(table_name)
        
        if not table_schema:
            return None
        
        for column in table_schema.get('columns', []):
            if column['name'].lower() == column_name.lower():
                return column
        
        return None
    
    def is_column_required(self, table_name: str, column_name: str) -> bool:
        """
        检查列是否必填
        
        Args:
            table_name: 表名
            column_name: 列名
        
        Returns:
            是否必填
        """
        column_info = self.get_column_info(table_name, column_name)
        
        if column_info:
            return column_info.get('required', False)
        
        return False
    
    def is_column_unique(self, table_name: str, column_name: str) -> bool:
        """
        检查列是否唯一
        
        Args:
            table_name: 表名
            column_name: 列名
        
        Returns:
            是否唯一
        """
        column_info = self.get_column_info(table_name, column_name)
        
        if column_info:
            return column_info.get('unique', False)
        
        return False
    
    def is_primary_key(self, table_name: str, column_name: str) -> bool:
        """
        检查列是否为主键
        
        Args:
            table_name: 表名
            column_name: 列名
        
        Returns:
            是否主键
        """
        column_info = self.get_column_info(table_name, column_name)
        
        if column_info:
            return column_info.get('primary_key', False)
        
        return False
    
    def get_foreign_key_tables(self, table_name: str) -> Dict[str, str]:
        """
        获取表的所有外键关系
        
        Args:
            table_name: 表名
        
        Returns:
            外键关系字典 {列名: 目标表(列名)}
        """
        table_schema = self.config_loader.get_table_schema(table_name)
        
        if not table_schema:
            return {}
        
        foreign_keys = {}
        
        for column in table_schema.get('columns', []):
            fk = column.get('foreign_key')
            if fk:
                foreign_keys[column['name']] = fk
        
        return foreign_keys
    
    def get_related_tables(self, table_name: str) -> List[str]:
        """
        获取与指定表相关的所有表
        
        Args:
            table_name: 表名
        
        Returns:
            相关表名列表
        """
        related_tables = set()
        
        # 检查当前表的外键
        table_schema = self.config_loader.get_table_schema(table_name)
        
        if table_schema:
            for column in table_schema.get('columns', []):
                fk = column.get('foreign_key')
                if fk:
                    # 格式: table_name(column_name)
                    match = re.match(r'(\w+)\(', fk)
                    if match:
                        related_tables.add(match.group(1))
        
        # 检查其他表的外键引用
        all_tables = self.get_all_table_names()
        
        for other_table in all_tables:
            if other_table.lower() == table_name.lower():
                continue
            
            other_schema = self.config_loader.get_table_schema(other_table)
            
            if other_schema:
                for column in other_schema.get('columns', []):
                    fk = column.get('foreign_key')
                    if fk:
                        # 检查是否引用当前表
                        if table_name.lower() in fk.lower():
                            related_tables.add(other_table)
        
        return list(related_tables)
    
    def estimate_affected_rows(self, sql: str) -> int:
        """
        预估SQL影响行数
        
        注意：这里只是简单的解析SQL，实际查询需要连接数据库
        
        Args:
            sql: SQL语句
        
        Returns:
            预估影响行数（-1表示未知，-2表示需要连接数据库查询）
        """
        try:
            sql_lower = sql.lower().strip()
            
            # 分析WHERE条件中的数值范围
            if sql_lower.startswith("update") or sql_lower.startswith("delete"):
                # 检查是否有明确的数量限制
                range_match = re.search(r'(\w+)\s*>=\s*(\d+)\s*and\s*\1\s*<=\s*(\d+)', sql_lower)
                if range_match:
                    start = int(range_match.group(2))
                    end = int(range_match.group(3))
                    estimated = end - start + 1
                    logger.debug(f"Estimated range: {start} to {end} = {estimated} rows")
                    return min(estimated, 1000)
                
                # 检查IN子句
                in_match = re.search(r'in\s*\(([^)]+)\)', sql_lower)
                if in_match:
                    values = in_match.group(1).split(',')
                    estimated = len(values)
                    logger.debug(f"Estimated IN clause: {estimated} rows")
                    return min(estimated, 1000)
                
                # 检查LIKE模式
                like_match = re.search(r"like\s+'([^']*)'", sql_lower)
                if like_match:
                    pattern = like_match.group(1)
                    # 估算匹配数量（这是一个粗略估计）
                    if '%' in pattern:
                        estimated = 10  # 通配符匹配，假设中等数量
                    else:
                        estimated = 1  # 精确匹配
                    logger.debug(f"Estimated LIKE: {estimated} rows")
                    return estimated
                
                # 无法预估，需要实际查询
                return -2
            
            elif sql_lower.startswith("insert"):
                # INSERT通常是插入一条或多条
                if "select" in sql_lower:
                    return -2  # INSERT SELECT需要查询
                else:
                    return 1  # 单条INSERT
            
            return -2  # 需要连接数据库查询
            
        except Exception as e:
            logger.error(f"Failed to estimate affected rows: {e}")
            return -2
    
    def format_schema_for_prompt(self) -> str:
        """
        格式化Schema为提示词友好的文本
        
        Returns:
            Schema文本
        """
        schema = self.config_loader.get_database_schema()
        
        lines = []
        lines.append(f"## 数据库Schema")
        lines.append(f"数据库名称: {schema.get('database_name', 'unknown')}")
        lines.append(f"数据库类型: {schema.get('database_type', 'unknown')}")
        lines.append(f"数据库描述: {schema.get('description', 'No description')}\n")
        
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
                if column.get('auto_increment'):
                    line += " [自增]"
                
                if 'description' in column:
                    line += f" - {column['description']}"
                
                lines.append(line)
            
            # 显示索引
            indexes = table.get('indexes', [])
            if indexes:
                lines.append("\n索引:")
                for idx in indexes:
                    idx_line = f"  - {idx['name']} on ({', '.join(idx['columns'])})"
                    if idx.get('unique'):
                        idx_line += " [唯一]"
                    lines.append(idx_line)
            
            lines.append("")
        
        return "\n".join(lines)
    
    def clear_cache(self):
        """清空缓存"""
        self._schema_cache = None
        self._table_cache.clear()
        logger.debug("Schema cache cleared")
