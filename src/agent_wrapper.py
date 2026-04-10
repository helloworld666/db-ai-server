"""
智能代理包装器 - 将Agent系统集成到MCP服务器中
"""

import json
import logging
from typing import Dict, Any, List
from src.agent_system import DatabaseAgent
from src.database_connector import DatabaseConnector
from src.lmstudio_client import LMStudioClient

logger = logging.getLogger(__name__)

class AgentWrapper:
    """智能代理包装器"""
    
    def __init__(self, config_loader):
        """
        初始化代理包装器
        
        Args:
            config_loader: 配置加载器
        """
        self.config_loader = config_loader
        self.agent = None
        self.initialized = False
        
    def initialize(self) -> bool:
        """初始化代理"""
        try:
            logger.info("正在初始化智能代理...")
            
            # 1. 获取数据库连接配置
            # 尝试多种可能的配置路径
            db_config = None
            config_paths = [
                "server.database.connection_string",  # 主配置路径
                "database.connection_string",         # 备用路径
                "server.database"                     # 整个数据库配置
            ]
            
            for path in config_paths:
                config_value = self.config_loader.get(path)
                if config_value:
                    logger.info(f"从路径 '{path}' 获取到数据库配置")
                    if path == "server.database" and isinstance(config_value, dict):
                        # 如果是字典，提取connection_string
                        db_config = config_value.get("connection_string")
                    else:
                        db_config = config_value
                    break
            
            if not db_config:
                logger.error("未找到数据库连接配置")
                # 记录所有可能的配置值用于调试
                for path in config_paths:
                    value = self.config_loader.get(path)
                    logger.debug(f"配置路径 '{path}': {value}")
                return False
            
            # 2. 获取AI配置
            inference_config = self.config_loader.get_inference_config()
            if not inference_config:
                logger.error("未找到AI推理配置")
                return False
            
            # 3. 初始化数据库连接器
            database_connector = DatabaseConnector(db_config)
            
            # 测试数据库连接
            connection_test = database_connector.test_connection()
            if not connection_test.get("connected"):
                logger.error(f"数据库连接失败: {connection_test.get('error')}")
                return False
            
            logger.info(f"数据库连接成功: {connection_test.get('database')} @ {connection_test.get('host')}:{connection_test.get('port')}")
            
            # 4. 初始化AI客户端
            ai_client = LMStudioClient(
                base_url=inference_config.get("base_url"),
                model=inference_config.get("model")
            )
            
            # 测试AI连接
            try:
                # 检查AI客户端是否有test_connection方法
                if hasattr(ai_client, 'test_connection'):
                    ai_test = ai_client.test_connection()
                    
                    # 如果是异步协程，需要特殊处理
                    import asyncio
                    if asyncio.iscoroutine(ai_test):
                        # 运行异步测试
                        ai_test_result = asyncio.run(ai_test)
                        if not ai_test_result.get("success"):
                            logger.error(f"AI客户端连接失败: {ai_test_result.get('error')}")
                            return False
                    elif isinstance(ai_test, dict):
                        # 同步测试结果
                        if not ai_test.get("success"):
                            logger.error(f"AI客户端连接失败: {ai_test.get('error')}")
                            return False
                    
                    logger.info(f"AI客户端连接成功: {inference_config.get('model')} @ {inference_config.get('base_url')}")
                else:
                    logger.warning("AI客户端没有test_connection方法，跳过连接测试")
                    
            except Exception as ai_error:
                logger.warning(f"AI连接测试可能有问题: {ai_error}")
                # 继续初始化，可能只是测试方法有问题
            
            # 5. 初始化智能代理
            self.agent = DatabaseAgent(database_connector, ai_client)
            
            self.initialized = True
            logger.info("智能代理初始化完成")
            
            return True
            
        except Exception as e:
            logger.error(f"初始化智能代理失败: {e}")
            return False
    
    def process_complete_operation(self, user_query: str) -> Dict[str, Any]:
        """
        处理完整操作：生成SQL、执行、验证、查询结果
        
        Args:
            user_query: 用户查询的自然语言描述
            
        Returns:
            包含完整操作结果和查询数据的响应
        """
        if not self.initialized or not self.agent:
            return {
                "success": False,
                "error": "代理未初始化",
                "message": "请先初始化代理"
            }
        
        try:
            logger.info(f"处理完整操作: {user_query}")
            
            # 使用代理处理请求
            result = self.agent.process_user_request(user_query)
            
            # 提取最终数据
            final_data = result.get("execution_result", {}).get("final_data")
            
            return {
                "success": True,
                "user_query": user_query,
                "agent_result": result,
                "operation_completed": result.get("execution_result", {}).get("success", False),
                "data_returned": final_data is not None,
                "data": final_data,
                "message": f"操作处理完成，{'已返回数据' if final_data else '未返回数据'}"
            }
            
        except Exception as e:
            logger.error(f"处理完整操作失败: {e}")
            return {
                "success": False,
                "user_query": user_query,
                "error": str(e),
                "message": f"处理失败: {str(e)}"
            }
    
    def intelligent_execute(self, user_query: str) -> Dict[str, Any]:
        """
        智能执行：分析用户意图，执行相应操作并返回结果
        
        这是主要的外部接口，C#客户端应调用此方法
        
        Args:
            user_query: 用户查询的自然语言描述
            
        Returns:
            标准化的响应格式
        """
        if not self.initialized or not self.agent:
            # 尝试初始化
            if not self.initialize():
                return {
                    "success": False,
                    "error": "系统初始化失败",
                    "message": "无法初始化数据库和AI连接"
                }
        
        try:
            logger.info(f"智能执行: {user_query}")
            
            # 分析用户意图
            intent = self._analyze_intent(user_query)
            logger.info(f"分析意图: {intent}")
            
            # 根据意图执行相应操作
            if intent == "insert":
                return self._handle_insert_operation(user_query)
            elif intent == "update":
                return self._handle_update_operation(user_query)
            elif intent == "delete":
                return self._handle_delete_operation(user_query)
            elif intent == "select":
                return self._handle_select_operation(user_query)
            else:
                # 通用处理
                return self.process_complete_operation(user_query)
                
        except Exception as e:
            logger.error(f"智能执行失败: {e}")
            return {
                "success": False,
                "user_query": user_query,
                "error": str(e),
                "message": f"执行失败: {str(e)}"
            }
    
    def _analyze_intent(self, user_query: str) -> str:
        """分析用户意图"""
        query_lower = user_query.lower()
        
        if any(word in query_lower for word in ["添加", "新增", "insert", "创建", "增加"]):
            return "insert"
        elif any(word in query_lower for word in ["修改", "更新", "update", "改变", "编辑"]):
            return "update"
        elif any(word in query_lower for word in ["删除", "delete", "移除", "去掉"]):
            return "delete"
        elif any(word in query_lower for word in ["查询", "查看", "select", "find", "搜索", "获取"]):
            return "select"
        else:
            return "unknown"
    
    def _handle_insert_operation(self, user_query: str) -> Dict[str, Any]:
        """处理插入操作"""
        logger.info(f"处理插入操作: {user_query}")
        
        # 1. 生成INSERT SQL
        generate_result = self.agent.tools["generate_sql"].execute_func(
            user_query=user_query,
            operation_type="insert"
        )
        
        if not generate_result.get("success"):
            return {
                "success": False,
                "operation": "insert",
                "error": generate_result.get("error"),
                "message": "生成SQL失败"
            }
        
        sql = generate_result.get("sql")
        logger.info(f"生成的INSERT SQL: {sql}")
        
        # 2. 执行INSERT
        execute_result = self.agent.tools["execute_sql"].execute_func(
            sql=sql,
            operation_type="insert"
        )
        
        if not execute_result.get("success"):
            return {
                "success": False,
                "operation": "insert",
                "sql": sql,
                "error": execute_result.get("error"),
                "message": "执行INSERT失败"
            }
        
        insert_id = execute_result.get("insert_id")
        affected_rows = execute_result.get("affected_rows", 0)
        
        logger.info(f"INSERT成功: insert_id={insert_id}, affected_rows={affected_rows}")
        
        # 3. 如果INSERT成功且有insert_id，查询新插入的数据
        if insert_id:
            # 查询新插入的数据
            query_sql = f"SELECT * FROM sys_user WHERE id = {insert_id}"
            query_result = self.agent.tools["execute_sql"].execute_func(
                sql=query_sql,
                operation_type="select"
            )
            
            if query_result.get("success"):
                data = query_result.get("data", [])
                return {
                    "success": True,
                    "operation": "insert",
                    "sql_generated": sql,
                    "sql_executed": sql,
                    "insert_id": insert_id,
                    "affected_rows": affected_rows,
                    "verification_query": query_sql,
                    "data": data,
                    "row_count": len(data),
                    "message": f"插入成功，新增数据ID: {insert_id}，已查询新插入的数据"
                }
        
        # 4. 如果没有insert_id，尝试其他方式查询
        # 这里可以添加更智能的查询逻辑
        
        return {
            "success": True,
            "operation": "insert",
            "sql_generated": sql,
            "sql_executed": sql,
            "affected_rows": affected_rows,
            "message": f"插入成功，影响 {affected_rows} 行数据",
            "note": "未查询到新插入的具体数据，可能需要手动查询验证"
        }
    
    def _handle_update_operation(self, user_query: str) -> Dict[str, Any]:
        """处理更新操作"""
        logger.info(f"处理更新操作: {user_query}")
        
        # 1. 生成UPDATE SQL
        generate_result = self.agent.tools["generate_sql"].execute_func(
            user_query=user_query,
            operation_type="update"
        )
        
        if not generate_result.get("success"):
            return {
                "success": False,
                "operation": "update",
                "error": generate_result.get("error"),
                "message": "生成SQL失败"
            }
        
        sql = generate_result.get("sql")
        logger.info(f"生成的UPDATE SQL: {sql}")
        
        # 2. 执行UPDATE
        execute_result = self.agent.tools["execute_sql"].execute_func(
            sql=sql,
            operation_type="update"
        )
        
        if not execute_result.get("success"):
            return {
                "success": False,
                "operation": "update",
                "sql": sql,
                "error": execute_result.get("error"),
                "message": "执行UPDATE失败"
            }
        
        affected_rows = execute_result.get("affected_rows", 0)
        
        logger.info(f"UPDATE成功: affected_rows={affected_rows}")
        
        # 3. 查询更新后的数据（需要从SQL中提取WHERE条件）
        # 这里简化处理，实际需要解析SQL
        table = "sys_user"  # 假设是sys_user表
        query_sql = f"SELECT * FROM {table} LIMIT 10"  # 简化查询
        
        query_result = self.agent.tools["execute_sql"].execute_func(
            sql=query_sql,
            operation_type="select"
        )
        
        if query_result.get("success"):
            data = query_result.get("data", [])
            return {
                "success": True,
                "operation": "update",
                "sql_generated": sql,
                "sql_executed": sql,
                "affected_rows": affected_rows,
                "verification_query": query_sql,
                "data": data[:5],  # 只返回前5条作为示例
                "row_count": len(data),
                "message": f"更新成功，影响 {affected_rows} 行数据，以下是示例数据"
            }
        
        return {
            "success": True,
            "operation": "update",
            "sql_generated": sql,
            "sql_executed": sql,
            "affected_rows": affected_rows,
            "message": f"更新成功，影响 {affected_rows} 行数据"
        }
    
    def _handle_select_operation(self, user_query: str) -> Dict[str, Any]:
        """处理查询操作"""
        logger.info(f"处理查询操作: {user_query}")
        
        # 1. 生成SELECT SQL
        generate_result = self.agent.tools["generate_sql"].execute_func(
            user_query=user_query,
            operation_type="select"
        )
        
        if not generate_result.get("success"):
            return {
                "success": False,
                "operation": "select",
                "error": generate_result.get("error"),
                "message": "生成SQL失败"
            }
        
        sql = generate_result.get("sql")
        logger.info(f"生成的SELECT SQL: {sql}")
        
        # 2. 执行查询
        execute_result = self.agent.tools["execute_sql"].execute_func(
            sql=sql,
            operation_type="select"
        )
        
        if not execute_result.get("success"):
            return {
                "success": False,
                "operation": "select",
                "sql": sql,
                "error": execute_result.get("error"),
                "message": "执行查询失败"
            }
        
        data = execute_result.get("data", [])
        row_count = len(data)
        
        logger.info(f"查询成功: 返回 {row_count} 行数据")
        
        return {
            "success": True,
            "operation": "select",
            "sql_generated": sql,
            "sql_executed": sql,
            "data": data,
            "row_count": row_count,
            "columns": list(data[0].keys()) if data else [],
            "message": f"查询成功，返回 {row_count} 行数据"
        }
    
    def _handle_delete_operation(self, user_query: str) -> Dict[str, Any]:
        """处理删除操作"""
        logger.info(f"处理删除操作: {user_query}")
        
        # 1. 生成DELETE SQL
        generate_result = self.agent.tools["generate_sql"].execute_func(
            user_query=user_query,
            operation_type="delete"
        )
        
        if not generate_result.get("success"):
            return {
                "success": False,
                "operation": "delete",
                "error": generate_result.get("error"),
                "message": "生成SQL失败"
            }
        
        sql = generate_result.get("sql")
        logger.info(f"生成的DELETE SQL: {sql}")
        
        # 2. 执行DELETE
        execute_result = self.agent.tools["execute_sql"].execute_func(
            sql=sql,
            operation_type="delete"
        )
        
        if not execute_result.get("success"):
            return {
                "success": False,
                "operation": "delete",
                "sql": sql,
                "error": execute_result.get("error"),
                "message": "执行DELETE失败"
            }
        
        affected_rows = execute_result.get("affected_rows", 0)
        
        logger.info(f"DELETE成功: affected_rows={affected_rows}")
        
        return {
            "success": True,
            "operation": "delete",
            "sql_generated": sql,
            "sql_executed": sql,
            "affected_rows": affected_rows,
            "message": f"删除成功，删除 {affected_rows} 行数据",
            "warning": "删除操作不可逆，请谨慎操作"
        }
    
    def get_agent_status(self) -> Dict[str, Any]:
        """获取代理状态"""
        return {
            "initialized": self.initialized,
            "agent_available": self.agent is not None,
            "tools_available": len(self.agent.tools) if self.agent else 0,
            "memory_entries": len(self.agent.memory) if self.agent else 0,
            "status": "ready" if self.initialized and self.agent else "not_ready"
        }
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        if not self.agent:
            return []
        
        return self.agent.get_tools_description()