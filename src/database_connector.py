"""
数据库连接器 - 负责数据库连接和SQL执行
"""

import logging
from typing import Dict, Any, Optional, List

try:
    import pymysql
    from pymysql.cursors import DictCursor
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False
    logging.warning("pymysql未安装，数据库功能将不可用。请运行: pip install pymysql")

logger = logging.getLogger(__name__)


class DatabaseConnector:
    """数据库连接器，负责SQL执行"""
    
    def __init__(self, connection_string: str):
        """
        初始化数据库连接器
        
        Args:
            connection_string: 数据库连接字符串
                格式: mysql://user:password@host:port/database
                或: mysql+pymysql://user:password@host:port/database
        """
        self.connection_string = connection_string
        self.connection = None
        self.connection_params = self._parse_connection_string()
        
        if not PYMYSQL_AVAILABLE:
            raise ImportError("pymysql未安装，请运行: pip install pymysql")
    
    def _parse_connection_string(self) -> Dict[str, str]:
        """
        解析连接字符串
        
        Args:
            connection_string: 连接字符串
            
        Returns:
            连接参数字典
        """
        # 移除可能的协议前缀
        conn_str = self.connection_string
        
        # 支持多种格式
        for prefix in ['mysql+pymysql://', 'mysql://', 'mysql+']:
            conn_str = conn_str.replace(prefix, '')
        
        # 分割用户密码和主机数据库
        try:
            # 格式: user:password@host:port/database
            parts = conn_str.split('@')
            if len(parts) != 2:
                raise ValueError(f"无效的连接字符串格式: {self.connection_string}")
            
            user_password = parts[0]
            host_port_db = parts[1]
            
            # 解析用户密码
            if ':' in user_password:
                user, password = user_password.split(':', 1)
            else:
                user = user_password
                password = ''
            
            # 解析主机端口数据库
            if '/' in host_port_db:
                host_port, database = host_port_db.split('/', 1)
            else:
                host_port = host_port_db
                database = ''
            
            # 解析主机端口
            if ':' in host_port:
                host, port = host_port.split(':', 1)
                port = int(port)
            else:
                host = host_port
                port = 3306  # MySQL默认端口
            
            return {
                'host': host,
                'port': port,
                'user': user,
                'password': password,
                'database': database
            }
        except Exception as e:
            logger.error(f"解析连接字符串失败: {e}")
            raise ValueError(f"无效的连接字符串: {self.connection_string}") from e
    
    def connect(self, force_new: bool = False) -> bool:
        """
        建立数据库连接
        
        Args:
            force_new: 是否强制创建新连接（忽略现有连接）
        
        Returns:
            是否连接成功
        """
        # 如果已有连接且不强制新建，先检查连接是否有效
        if self.connection and not force_new:
            if self._is_connection_alive():
                return True
            else:
                logger.info("检测到失效连接，尝试重新连接...")
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
                autocommit=False,  # 需要手动提交事务
                # 连接保活参数
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30,
            )
            logger.info(f"成功连接到数据库: {self.connection_params['database']} @ {self.connection_params['host']}:{self.connection_params['port']}")
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False
    
    def _is_connection_alive(self) -> bool:
        """
        检查数据库连接是否存活
        
        Returns:
            连接是否有效
        """
        if not self.connection:
            return False
        
        try:
            self.connection.ping(reconnect=True)
            return True
        except Exception as e:
            logger.warning(f"连接存活检查失败: {e}")
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("数据库连接已关闭")
    
    def _ensure_connection(self) -> bool:
        """
        确保数据库连接有效，必要时重新连接
        
        Returns:
            连接是否可用
        """
        if not self.connection or not self._is_connection_alive():
            return self.connect()
        return True
    
    def execute_query(self, sql: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """
        执行SELECT查询

        Args:
            sql: SQL语句
            params: 查询参数（防止SQL注入）

        Returns:
            查询结果字典，包含rows、affected_rows、columns、column_comments等信息
        """
        # 确保连接有效
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

            # 执行查询
            cursor.execute(sql, params or ())

            # 获取结果
            rows = cursor.fetchall()
            affected_rows = cursor.rowcount

            # 获取列名
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # 获取字段注释信息
            column_comments = self._get_column_comments(sql, columns) if columns else {}

            logger.info(f"执行查询成功，返回 {len(rows)} 行，影响 {affected_rows} 行")

            return {
                'success': True,
                'rows': rows,
                'affectedRows': affected_rows,
                'columns': columns,
                'columnComments': column_comments,
                'rowCount': len(rows)
            }

        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            logger.error(f"SQL: {sql}")
            return {
                'success': False,
                'error': str(e),
                'rows': [],
                'affected_rows': 0
            }
        finally:
            if cursor:
                cursor.close()

    def _get_column_comments(self, sql: str, columns: list) -> Dict[str, str]:
        """
        获取字段注释

        Args:
            sql: SQL语句
            columns: 列名列表

        Returns:
            字段注释字典 {列名: 注释}
        """
        comments = {}

        try:
            # 从SQL中提取表名
            table_name = self._extract_table_name(sql)

            if not table_name:
                logger.info(f"无法从SQL中提取表名，返回空注释")
                return comments

            # 查询字段注释
            comment_sql = """
                SELECT COLUMN_NAME, COLUMN_COMMENT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """

            cursor = self.connection.cursor()
            cursor.execute(comment_sql, (
                self.connection_params['database'],
                table_name
            ))
            comment_rows = cursor.fetchall()
            cursor.close()

            # 构建注释字典
            for row in comment_rows:
                col_name = row['COLUMN_NAME']
                col_comment = row['COLUMN_COMMENT'] or ''  # 如果注释为空则返回空字符串

                # 只返回查询中的字段注释
                if col_name in columns:
                    comments[col_name] = col_comment

            logger.info(f"获取字段注释成功，共 {len(comments)} 个字段")

        except Exception as e:
            logger.warning(f"获取字段注释失败: {e}")

        return comments

    def _extract_table_name(self, sql: str) -> Optional[str]:
        """
        从SQL语句中提取主表名

        Args:
            sql: SQL语句

        Returns:
            表名（仅支持单表查询）
        """
        import re

        try:
            # 移除注释
            sql = re.sub(r'--.*?\n', '', sql)
            sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

            # 提取FROM和JOIN后的表名
            # 匹配 FROM table_name 或 JOIN table_name
            pattern = r'\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            matches = re.findall(pattern, sql, re.IGNORECASE)

            if matches:
                # 返回第一个匹配的表名（主表）
                return matches[0]

            return None

        except Exception as e:
            logger.warning(f"提取表名失败: {e}")
            return None
    
    def execute_update(self, sql: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """
        执行INSERT/UPDATE/DELETE操作
        
        Args:
            sql: SQL语句
            params: 查询参数（防止SQL注入）
        
        Returns:
            执行结果字典，包含success、affected_rows、insert_id等信息
        """
        # 确保连接有效
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
            
            # 执行SQL
            affected_rows = cursor.execute(sql, params or ())
            
            # 获取自增ID（仅对INSERT有效）
            insert_id = cursor.lastrowid if 'insert' in sql.lower() else None
            
            # 提交事务
            self.connection.commit()
            
            logger.info(f"执行更新成功，影响 {affected_rows} 行，insert_id={insert_id}")
            
            return {
                'success': True,
                'affectedRows': affected_rows,
                'insertId': insert_id
            }
            
        except Exception as e:
            # 回滚事务
            if self.connection:
                self.connection.rollback()
            
            logger.error(f"执行更新失败: {e}")
            logger.error(f"SQL: {sql}")
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
        """
        执行任意SQL语句（自动识别查询/更新类型）
        
        Args:
            sql: SQL语句
            params: 查询参数
        
        Returns:
            执行结果字典
        """
        sql_upper = sql.upper().strip()
        
        # 判断SQL类型
        if sql_upper.startswith('SELECT'):
            return self.execute_query(sql, params)
        else:
            return self.execute_update(sql, params)
    
    def test_connection(self) -> Dict[str, Any]:
        """
        测试数据库连接
        
        Returns:
            测试结果字典
        """
        try:
            # 确保连接有效
            if not self._ensure_connection():
                return {
                    'connected': False,
                    'error': '数据库连接失败'
                }

            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()

            # 获取数据库版本信息
            cursor = self.connection.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            cursor.close()

            return {
                'connected': True,
                'database': self.connection_params['database'],
                'host': self.connection_params['host'],
                'port': self.connection_params['port'],
                'user': self.connection_params['user'],
                'version': version.get('VERSION()') if version else 'Unknown'
            }
            
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }
    
    def get_table_info(self) -> List[Dict[str, Any]]:
        """
        获取数据库中所有表的信息
        
        Returns:
            表信息列表
        """
        # 确保连接有效
        if not self._ensure_connection():
            return []
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            cursor.close()
            
            result = []
            for table in tables:
                table_name = list(table.values())[0]
                
                # 获取表结构
                cursor = self.connection.cursor()
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                cursor.close()
                
                result.append({
                    'name': table_name,
                    'columns': columns
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取表信息失败: {e}")
            return []
    
    def execute_transaction(self, sql_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        执行事务（多条SQL）
        
        Args:
            sql_list: SQL语句列表，每项包含 {sql: str, params: tuple}
        
        Returns:
            事务执行结果
        """
        # 确保连接有效
        if not self._ensure_connection():
            return {
                'success': False,
                'error': '数据库连接失败',
                'results': []
            }
        
        cursor = None
        results = []
        
        try:
            cursor = self.connection.cursor()
            
            for i, sql_item in enumerate(sql_list):
                sql = sql_item.get('sql', '')
                params = sql_item.get('params', ())
                
                affected_rows = cursor.execute(sql, params)
                results.append({
                    'index': i,
                    'success': True,
                    'affected_rows': affected_rows
                })
            
            # 提交事务
            self.connection.commit()
            
            logger.info(f"事务执行成功，共 {len(sql_list)} 条SQL")
            
            return {
                'success': True,
                'results': results,
                'totalAffectedRows': sum(r['affected_rows'] for r in results)
            }
            
        except Exception as e:
            # 回滚事务
            if self.connection:
                self.connection.rollback()
            
            logger.error(f"事务执行失败: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'results': results
            }
        finally:
            if cursor:
                cursor.close()
    
    def __enter__(self):
        """支持上下文管理器"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器"""
        self.disconnect()
