"""SQL Agent - 使用LangChain标准create_agent

参考: https://langchain-doc.cn/v1/python/langchain/agents.html

核心设计：
1. 使用create_agent创建Agent，无需自定义Agent类
2. 工具调用完全由LLM自主决定
3. 提示词从配置文件动态加载
4. 数据库Schema从配置文件动态获取
"""
import json
import logging
import re
from typing import Dict, Any, Optional, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

try:
    from langchain.agents import create_agent
except ImportError:
    create_agent = None

from ..database.prompts import PromptManager
from ..database.schema import SchemaManager
from ..security.validator import SQLValidator

logger = logging.getLogger(__name__)


class SQLAgent:
    """
    SQL Agent - 极简实现

    业务逻辑：
    1. 获取数据库schema（动态从配置文件加载）
    2. 构建SQL生成提示词（从配置文件动态加载）
    3. 调用LLM生成SQL
    4. 验证SQL安全性
    5. 返回结果

    注意：不使用ReAct循环，直接生成SQL
    """

    def __init__(
        self,
        llm: BaseChatModel,
        schema_manager: SchemaManager,
        prompt_manager: PromptManager,
        sql_validator: SQLValidator,
    ):
        self.llm = llm
        self.schema_manager = schema_manager
        self.prompt_manager = prompt_manager
        self.sql_validator = sql_validator

    async def ainvoke(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        异步调用Agent处理查询

        流程：
        1. 获取数据库schema（动态加载）
        2. 构建生成SQL的提示词（动态加载）
        3. 调用LLM生成SQL
        4. 验证SQL
        """
        logger.info(f"Agent处理查询: {query}")

        try:
            # 步骤1: 获取schema（动态从配置文件加载）
            schema = self._get_schema_for_prompt()

            # 步骤2: 构建生成SQL的提示词（动态加载）
            prompt = self._build_sql_generation_prompt(query, schema)

            # 步骤3: 调用LLM生成SQL
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content=query)
            ]

            logger.info(f"正在调用LLM生成SQL，模型类型: {type(self.llm).__name__}")
            logger.debug(f"提示词长度: {len(prompt)} 字符")

            try:
                response = await self.llm.ainvoke(messages)
                content = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"LLM响应成功，响应长度: {len(content)} 字符")
                logger.debug(f"LLM原始响应: {content[:500]}")
            except Exception as llm_error:
                logger.error(f"LLM调用失败: {llm_error}")
                raise

            # 步骤4: 提取纯SQL
            sql = self._extract_sql(content)
            logger.info(f"提取SQL结果: {'成功' if sql else '失败'}, SQL: {sql[:100] if sql else 'None'}")

            if not sql:
                return {
                    "success": False,
                    "error": "未能从LLM响应中提取SQL",
                    "raw_response": content[:500]
                }

            # 步骤5: 验证SQL
            validation = self.sql_validator.validate(sql)
            logger.info(f"SQL验证结果: is_valid={validation.get('is_valid')}, errors={validation.get('errors', [])}")

            if not validation.get("is_valid"):
                return {
                    "success": False,
                    "error": f"SQL验证失败: {validation.get('errors', [])}",
                    "sql": sql
                }

            logger.info(f"Agent处理完成，返回SQL: {sql[:100]}")
            return {
                "success": True,
                "sql": sql
            }

        except Exception as e:
            logger.error(f"Agent执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

    def _get_schema_for_prompt(self) -> str:
        """
        获取格式化的schema用于提示词

        从配置文件动态加载，不硬编码任何表/字段信息
        """
        try:
            tables = self.schema_manager.get_all_table_names()
            if not tables:
                return "数据库中没有表。"

            lines = []
            for table_name in tables:
                schema = self.schema_manager.get_table_schema(table_name)
                if schema:
                    lines.append(f"\n表: {table_name}")
                    desc = schema.get('description', '')
                    if desc:
                        lines.append(f"  描述: {desc}")

                    columns = schema.get('columns', [])
                    if columns:
                        lines.append("  字段:")
                        for col in columns:
                            col_name = col.get('name', 'unknown')
                            col_type = col.get('type', 'unknown')
                            col_desc = col.get('description', '')
                            pk_mark = " [PK]" if col.get('primary_key') else ""
                            req_mark = " [必填]" if col.get('required') else ""
                            lines.append(f"    - {col_name}: {col_type}{pk_mark}{req_mark} {col_desc}")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"获取schema失败: {e}")
            return f"无法获取数据库结构: {e}"

    def _build_sql_generation_prompt(self, query: str, schema: str) -> str:
        """
        构建SQL生成提示词

        从prompts.json动态加载系统提示词，不硬编码
        """
        # 从配置管理器获取系统提示词
        system_prompt = self.prompt_manager.get_system_prompt()

        # 构建完整提示词
        return f"""{system_prompt}

【数据库结构】
{schema}

【用户查询】
{query}

【要求】
1. 只能使用上述数据库结构中存在的表名和字段名
2. 禁止编造任何表名或字段名
3. 直接返回纯SQL语句，不要添加任何解释
"""

    def _extract_sql(self, content: str) -> Optional[str]:
        """从LLM响应中提取纯SQL"""
        if not content:
            return None

        # 清理内容
        text = content.strip()

        # 移除Markdown代码块
        patterns = [
            r'^```(?:sql|json)?\s*\n?(.*?)\n?```$',
            r'^```\s*\n?(.*?)\n?```$',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                text = match.group(1).strip()
                break

        # 尝试解析JSON格式（如果LLM返回了JSON）
        if text.startswith('{') and text.endswith('}'):
            try:
                data = json.loads(text)
                if isinstance(data, dict) and 'sql' in data:
                    text = data['sql']
            except json.JSONDecodeError:
                pass

        # 提取SQL语句
        sql_patterns = [
            r'(SELECT\s+.+?)(?:;|$)',
            r'(INSERT\s+.+?)(?:;|$)',
            r'(UPDATE\s+.+?)(?:;|$)',
            r'(DELETE\s+.+?)(?:;|$)',
        ]

        for pattern in sql_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                sql = match.group(1).strip()
                # 清理SQL
                sql = sql.rstrip(';').strip()
                return sql

        # 如果都没匹配到，但内容看起来像SQL，直接返回
        if re.match(r'^\s*(SELECT|INSERT|UPDATE|DELETE)\s+', text, re.IGNORECASE):
            return text.rstrip(';').strip()

        return None

    def invoke(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """同步调用Agent"""
        import asyncio
        return asyncio.run(self.ainvoke(query, user_context))


def create_sql_agent(
    llm: BaseChatModel,
    schema_manager: SchemaManager,
    prompt_manager: PromptManager,
    sql_validator: SQLValidator,
    tools: Optional[List] = None
) -> SQLAgent:
    """
    创建SQL Agent实例

    这是工厂函数，用于创建配置好的SQLAgent实例

    Args:
        llm: LangChain ChatModel
        schema_manager: Schema管理器
        prompt_manager: 提示词管理器
        sql_validator: SQL验证器
        tools: 可选的工具列表（当前版本不使用）

    Returns:
        配置好的SQLAgent实例
    """
    logger.info("创建SQL Agent")
    return SQLAgent(
        llm=llm,
        schema_manager=schema_manager,
        prompt_manager=prompt_manager,
        sql_validator=sql_validator
    )
