"""数据库连接管理"""
import logging
import re
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime, date, time
from decimal import Decimal

if TYPE_CHECKING:
    from ..schema.manager import SchemaManager

logger = logging.getLogger(__name__)

# PyMySQL依赖检查
try:
    import pymysql
    from pymysql.cursors import DictCursor
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False
    logger.warning("pymysql未安装，数据库功能将不可用")


class DatabaseConnection:
    """数据库连接管理器"""

    def __init__(self, connection_string: str, schema_manager: Optional["SchemaManager"] = None):
        """初始化数据库连接器

        Args:
            connection_string: 数据库连接字符串
            schema_manager: Schema管理器，用于显示映射配置
        """
        if not PYMYSQL_AVAILABLE:
            raise ImportError("pymysql未安装，请运行: pip install pymysql")

        self.connection_string = connection_string
        self.connection = None
        self.connection_params = self._parse_connection_string(connection_string)
        self._schema_manager = schema_manager

    def _parse_connection_string(self, conn_str: str) -> Dict[str, Any]:
        """解析连接字符串"""
        for prefix in ['mysql+pymysql://', 'mysql://']:
            conn_str = conn_str.replace(prefix, '')

        parts = conn_str.split('@')
        if len(parts) != 2:
            raise ValueError(f"无效的连接字符串格式: {conn_str}")

        user_password = parts[0]
        host_port_db = parts[1]

        if ':' in user_password:
            user, password = user_password.split(':', 1)
        else:
            user, password = user_password, ''

        if '/' in host_port_db:
            host_port, database = host_port_db.split('/', 1)
        else:
            host_port, database = host_port_db, ''

        if ':' in host_port:
            host, port = host_port.split(':')
            port = int(port)
        else:
            host, port = host_port, 3306

        return {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database
        }

    def connect(self, force_new: bool = False) -> bool:
        """建立数据库连接"""
        if self.connection and not force_new:
            if self._is_connection_alive():
                return True
            self.disconnect()

        try:
            self.connection = pymysql.connect(
                host=self.connection_params['host'],
                port=self.connection_params['port'],
                user=self.connection_params['user'],
                password=self.connection_params['password'],
                database=self.connection_params['database'],
                cursorclass=DictCursor,
                charset='utf8mb4',
                autocommit=False,
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30,
            )
            logger.info(f"已连接到数据库: {self.connection_params['database']}")
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False

    def _is_connection_alive(self) -> bool:
        """检查连接是否存活"""
        if not self.connection:
            return False
        try:
            self.connection.ping(reconnect=True)
            return True
        except Exception:
            return False

    def disconnect(self):
        """断开连接"""
        if self.connection:
            self.connection.close()
            self.connection = None

    def _ensure_connection(self) -> bool:
        """确保连接有效"""
        if not self.connection or not self._is_connection_alive():
            return self.connect()
        return True

    def _convert_datetimes(self, rows: List[Dict]) -> List[Dict]:
        """转换datetime对象为ISO格式字符串"""
        converted_rows = []
        for row in rows:
            converted_row = {}
            for key, value in row.items():
                if isinstance(value, datetime):
                    converted_row[key] = value.isoformat()
                elif isinstance(value, date):
                    converted_row[key] = value.isoformat()
                elif isinstance(value, time):
                    converted_row[key] = value.isoformat()
                elif isinstance(value, Decimal):
                    converted_row[key] = float(value)
                else:
                    converted_row[key] = value
            converted_rows.append(converted_row)
        return converted_rows

    def _apply_chinese_column_names(
        self,
        sql: str,
        columns: List[str],
        column_comments: Dict[str, str],
        rows: List[Dict]
    ) -> tuple:
        """使用 schema_manager 中的中文描述替换英文列名

        优先级：
        1. schema_manager 中列的 description（配置文件）
        2. 数据库 COLUMN_COMMENT
        3. 原始列名

        Args:
            sql: SQL语句（用于提取表名）
            columns: 原始列名列表
            column_comments: 列名到注释的映射
            rows: 数据行

        Returns:
            (新列名列表, 新注释映射, 新数据行)
        """
        logger.info(f"[中文列名] 原始列名: {columns}")
        logger.info(f"[中文列名] 列注释: {column_comments}")

        # 获取SQL中涉及的表名
        table_names = self._extract_all_table_names(sql)
        logger.info(f"[中文列名] 涉及的表名: {table_names}")

        # 收集所有列的中文描述
        chinese_names = {}
        has_chinese = False

        for col in columns:
            chinese_desc = None

            # 1. 优先使用 output_name（专门的输出名称）
            if self._schema_manager and table_names:
                for table_name in table_names:
                    col_info = self._schema_manager.get_column_info(table_name, col)
                    if col_info:
                        # 优先用 output_name
                        if col_info.get('output_name'):
                            chinese_desc = col_info['output_name']
                            logger.info(f"[中文列名] {table_name}.{col} 使用output_name: {chinese_desc}")
                            break
                        # 其次用 description
                        elif col_info.get('description'):
                            chinese_desc = col_info['description']
                            logger.info(f"[中文列名] {table_name}.{col} 使用description: {chinese_desc}")
                            break

            # 2. 其次使用数据库的 COLUMN_COMMENT
            if not chinese_desc and col in column_comments and column_comments[col]:
                chinese_desc = column_comments[col]

            # 3. 记录中文描述
            if chinese_desc:
                chinese_names[col] = chinese_desc
                has_chinese = True

        if not has_chinese:
            logger.info("[中文列名] 没有列有中文描述，保持原样")
            return columns, column_comments, rows

        # 用中文列名替换英文列名
        new_columns = []
        new_column_comments = {}
        for col in columns:
            if col in chinese_names:
                new_columns.append(chinese_names[col])
                new_column_comments[chinese_names[col]] = chinese_names[col]
            else:
                new_columns.append(col)
                new_column_comments[col] = column_comments.get(col, '')

        # 重命名 rows 中的键
        new_rows = []
        for row in rows:
            new_row = {}
            for col in columns:
                if col in chinese_names:
                    new_row[chinese_names[col]] = row.get(col)
                else:
                    new_row[col] = row.get(col)
            new_rows.append(new_row)

        logger.info(f"[中文列名] 转换后的列名: {new_columns}")
        return new_columns, new_column_comments, new_rows

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """执行SELECT查询"""
        if not self._ensure_connection():
            return {
                'success': False,
                'error': '数据库连接失败',
                'rows': [],
                'affected_rows': 0
            }

        cursor = None
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            affected_rows = cursor.rowcount
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = self._convert_datetimes(rows)

            column_comments = self._get_column_comments(sql, columns)

            # 总是应用中文列名（优先使用 schema_manager 中的描述）
            columns, column_comments, rows = self._apply_chinese_column_names(sql, columns, column_comments, rows)

            # 应用 display_mapping 配置的值转换（仅在 _schema_manager 存在时）
            if self._schema_manager:
                rows, columns, column_comments = self._apply_display_mappings(sql, rows, columns, column_comments)

            return {
                'success': True,
                'rows': rows,
                'affected_rows': affected_rows,
                'columns': columns,
                'column_comments': column_comments,
                'row_count': len(rows)
            }

        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'rows': [],
                'affected_rows': 0
            }
        finally:
            if cursor:
                cursor.close()

    def _apply_display_mappings(
        self,
        sql: str,
        rows: List[Dict],
        columns: List[str],
        column_comments: Dict[str, str]
    ) -> tuple:
        """应用显示映射配置（列名翻译和值转换）

        优先级：
        1. display_mapping 的 output_name（配置优先）
        2. column_comments 中的中文注释
        3. 原始列名

        Args:
            sql: SQL语句
            rows: 原始数据行
            columns: 原始列名
            column_comments: 列注释

        Returns:
            转换后的 (rows, columns, column_comments)
        """
        # 获取SQL中涉及的所有表名
        table_names = self._extract_all_table_names(sql)
        logger.info(f"[DisplayMapping] SQL: {sql}")
        logger.info(f"[DisplayMapping] 提取的表名: {table_names}")
        logger.info(f"[DisplayMapping] 原始列名: {columns}")
        logger.info(f"[DisplayMapping] 列注释: {column_comments}")

        if not table_names:
            logger.info("[DisplayMapping] 未提取到表名，跳过映射")
            return rows, columns, column_comments

        # 收集需要 display_mapping 的字段配置（用于值转换）
        # display_mapping 配置使用原始英文列名作为 key
        column_mappings: Dict[str, Dict[str, Any]] = {}
        
        for table_name in table_names:
            mappings = self._schema_manager.get_table_display_mappings(table_name)
            for col_name, mapping in mappings.items():
                column_mappings[col_name] = mapping

        logger.info(f"[DisplayMapping] display_mapping 配置: {column_mappings}")

        # 如果没有需要转换值的字段，直接返回
        if not column_mappings:
            return rows, columns, column_comments

        # 建立中文列名到原始列名的反向映射
        # 输出名称可能来自 output_name 或 description，需要同时匹配
        english_to_chinese: Dict[str, str] = {}
        english_to_output_name: Dict[str, str] = {}
        for table_name in table_names:
            table_schema = self._schema_manager.get_table_schema(table_name)
            if table_schema:
                for col in table_schema.get('columns', []):
                    col_name = col['name']
                    output_name = col.get('output_name', '')
                    desc = col.get('description', '')
                    if col_name in columns:
                        # 原始列名 -> output_name（优先）
                        if output_name:
                            english_to_output_name[col_name] = output_name
                        # 原始列名 -> description（备用）
                        if desc:
                            english_to_chinese[col_name] = desc

        logger.info(f"[DisplayMapping] 英文到output_name映射: {english_to_output_name}")
        logger.info(f"[DisplayMapping] 英文到description映射: {english_to_chinese}")

        # 转换每行数据中的值（布尔值等）
        converted_rows = []
        for row in rows:
            converted_row = {}
            for col in columns:
                value = row.get(col)

                # 找到原始英文列名（优先使用 output_name 匹配）
                original_col = col
                matched = False

                # 先用 output_name 匹配（更精确）
                for eng, out_name in english_to_output_name.items():
                    if out_name == col:
                        original_col = eng
                        matched = True
                        break

                # 如果没匹配到，再用 description 匹配（去除后缀后匹配）
                if not matched:
                    for eng, desc in english_to_chinese.items():
                        # 去除 "：1-可用，0-不可用" 等后缀
                        base_desc = desc.split('：')[0].split('(')[0].strip()
                        base_col = col.split('：')[0].split('(')[0].strip()
                        if base_desc == base_col:
                            original_col = eng
                            break

                # 检查是否有 display_mapping
                if original_col in column_mappings and column_mappings[original_col].get('display_mapping'):
                    display_map = column_mappings[original_col]['display_mapping']
                    value_str = str(value) if value is not None else ''
                    if value_str in display_map:
                        value = display_map[value_str]
                        logger.info(f"[DisplayMapping] 列 {col}({original_col}) 值 {value_str} -> {value}")

                converted_row[col] = value
            converted_rows.append(converted_row)

        return converted_rows, columns, column_comments

    def _get_column_comments(self, sql: str, columns: List[str]) -> Dict[str, str]:
        """获取字段注释"""
        comments = {}
        try:
            table_names = self._extract_all_table_names(sql)
            if not table_names:
                return comments

            comment_sql = """
                SELECT TABLE_NAME, COLUMN_NAME, COLUMN_COMMENT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({})
            """.format(', '.join(['%s'] * len(table_names)))

            cursor = self.connection.cursor()
            params = [self.connection_params['database']] + table_names
            cursor.execute(comment_sql, tuple(params))
            comment_rows = cursor.fetchall()
            cursor.close()

            for row in comment_rows:
                col_name = row['COLUMN_NAME']
                if col_name in columns:
                    comments[col_name] = row['COLUMN_COMMENT'] or ''

        except Exception as e:
            logger.warning(f"获取字段注释失败: {e}")

        return comments

    def _extract_all_table_names(self, sql: str) -> List[str]:
        """从SQL中提取所有表名"""
        try:
            sql = re.sub(r'--.*?\n', '', sql)
            sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
            sql = re.sub(r'\(SELECT.*?FROM.*?\)', '(SELECT ...)', sql, flags=re.IGNORECASE | re.DOTALL)
            pattern = r'\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+(?:AS\s+)?[a-zA-Z_][a-zA-Z0-9_]*)?\b'
            matches = re.findall(pattern, sql, re.IGNORECASE)
            return list(set(matches)) if matches else []
        except Exception:
            return []

    def execute_update(self, sql: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """执行INSERT/UPDATE/DELETE操作"""
        if not self._ensure_connection():
            return {
                'success': False,
                'error': '数据库连接失败',
                'affected_rows': 0,
                'insert_id': None
            }

        cursor = None
        try:
            cursor = self.connection.cursor()
            affected_rows = cursor.execute(sql, params)
            insert_id = cursor.lastrowid if 'insert' in sql.lower() else None
            self.connection.commit()

            return {
                'success': True,
                'affected_rows': affected_rows,
                'insert_id': insert_id
            }

        except Exception as e:
            if self.connection:
                self.connection.rollback()
            logger.error(f"执行更新失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'affected_rows': 0,
                'insert_id': None
            }
        finally:
            if cursor:
                cursor.close()

    def execute_sql(self, sql: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """执行SQL（自动识别类型）"""
        sql_upper = sql.upper().strip()
        if sql_upper.startswith('SELECT'):
            return self.execute_query(sql, params)
        else:
            return self.execute_update(sql, params)

    def execute_multi_step(self, main_sql: str, follow_up_sql: str) -> Dict[str, Any]:
        """执行多步SQL（主SQL + 验证查询）"""
        main_result = self.execute_update(main_sql, None)
        if not main_result.get('success'):
            return {
                'success': False,
                'error': main_result.get('error'),
                'main_execution': main_result,
                'follow_up_execution': None
            }

        follow_up_result = self.execute_query(follow_up_sql, None)

        return {
            'success': True,
            'main_execution': main_result,
            'follow_up_execution': follow_up_result,
            'error': None
        }

    def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            if not self._ensure_connection():
                return {'connected': False, 'error': '连接失败'}

            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()

            return {
                'connected': True,
                'database': self.connection_params['database'],
                'host': self.connection_params['host'],
                'port': self.connection_params['port'],
            }

        except Exception as e:
            return {'connected': False, 'error': str(e)}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
