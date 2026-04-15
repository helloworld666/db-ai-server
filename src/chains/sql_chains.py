"""SQL生成Chain - 使用LCEL"""
import json
import logging
from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough

from ..database.schema import SchemaManager
from ..database.prompts import PromptManager
from ..security.validator import SQLValidator

logger = logging.getLogger(__name__)


class SQLGenerationChain:
    """
    SQL生成Chain - 基于LCEL的声明式组合

    特点：
    1. 完全由LCEL组合，无硬编码逻辑
    2. 提示词从配置文件动态加载
    3. 输出结构化JSON
    """

    def __init__(
        self,
        llm,
        schema_manager: SchemaManager,
        prompt_manager: PromptManager,
        sql_validator: SQLValidator
    ):
        """
        初始化SQL生成Chain

        Args:
            llm: LangChain兼容的LLM
            schema_manager: Schema管理器
            prompt_manager: 提示词管理器
            sql_validator: SQL验证器
        """
        self.llm = llm
        self.schema_manager = schema_manager
        self.prompt_manager = prompt_manager
        self.sql_validator = sql_validator

        # 构建Chain
        self.chain = self._build_chain()

    def _build_chain(self):
        """构建LCEL Chain"""
        # 输入准备
        def prepare_inputs(inputs: Dict) -> Dict:
            """准备输入数据"""
            query = inputs.get("query", "")
            user_context = inputs.get("user_context", {})

            # 获取表结构
            schema_summary = self.schema_manager.get_table_summary()
            schema_text = "\n".join([
                f"- {t['table']}: {t['description']}"
                for t in schema_summary
            ])

            # 获取业务规则
            business_rules = self.prompt_manager.get_business_rules()
            business_rules_text = "\n".join([
                f"- {table}: {rule}"
                for table, rule in business_rules.items()
            ])

            return {
                "query": query,
                "user_context": user_context,
                "database_structure": schema_text,
                "business_rules": business_rules_text
            }

        # 提示词模板
        prompt = ChatPromptTemplate.from_template(
            self.prompt_manager.get_sql_generation_prompt(
                database_structure="{database_structure}",
                query="{query}",
                business_rules="{business_rules}"
            )
        )

        # SQL验证
        def validate_and_enrich(result: Dict) -> Dict:
            """验证并丰富结果"""
            sql = result.get("sql", "")

            # 验证SQL
            validation = self.sql_validator.validate(sql)
            result["validation"] = validation

            # 评估风险
            sql_type = validation.get("sql_type", "")
            estimated_rows = self.schema_manager.estimate_affected_rows(sql)
            risk_level = self.sql_validator.evaluate_risk(sql, sql_type, estimated_rows)
            result["risk_level"] = risk_level

            # 生成建议
            suggestions = self.sql_validator.generate_suggestions(sql, sql_type)
            if suggestions:
                result["suggestions"] = suggestions

            return result

        # 构建完整Chain
        chain = (
            RunnablePassthrough.assign(
                schema_and_rules=lambda x: prepare_inputs(x)
            )
            | RunnableParallel(
                schema=lambda x: x["schema_and_rules"]["database_structure"],
                query=lambda x: x["schema_and_rules"]["query"],
                business_rules=lambda x: x["schema_and_rules"]["business_rules"]
            )
            | {
                "prompt_input": RunnablePassthrough.assign(
                    full_prompt=lambda x: self.prompt_manager.get_sql_generation_prompt(
                        database_structure=x["schema"],
                        query=x["query"],
                        business_rules=x["business_rules"]
                    )
                ),
                "original_query": lambda x: x["query"]
            }
            | RunnablePassthrough.assign(
                llm_response=lambda x: self.llm.invoke(x["full_prompt"])
            )
            | self._parse_llm_response
            | validate_and_enrich
        )

        return chain

    def _parse_llm_response(self, inputs: Dict) -> Dict:
        """解析LLM响应"""
        import re

        response = inputs.get("llm_response", {})
        if hasattr(response, 'content'):
            text = response.content
        else:
            text = str(response)

        # 尝试解析JSON
        text = re.sub(r'```sql\n?', '', text)
        text = re.sub(r'```\n?', '', text)
        text = text.strip()

        if text.startswith('{'):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        return {"sql": text, "error": "无法解析LLM响应"}

    async def ainvoke(self, query: str, user_context: Optional[Dict] = None) -> Dict:
        """异步调用Chain"""
        inputs = {
            "query": query,
            "user_context": user_context or {}
        }
        return await self.chain.ainvoke(inputs)

    def invoke(self, query: str, user_context: Optional[Dict] = None) -> Dict:
        """同步调用Chain"""
        inputs = {
            "query": query,
            "user_context": user_context or {}
        }
        return self.chain.invoke(inputs)
