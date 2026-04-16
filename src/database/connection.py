"""数据库连接管理"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date, time
from decimal import Decimal

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

    def __init__(self, connection_string: str):
        """初始化数据库连接器"""
        if not PYMYSQL_AVAILABLE:
            raise ImportError("pymysql未安装，请运行: pip install pymysql")

        self.connection_string = connection_string
        self.connection = None
        self.connection_params = self._parse_connection_string(connection_string)

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
        import re
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
