"""验证链 - LCEL实现"""
import json
import logging
from typing import Dict, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from ..security.validator import SQLValidator

logger = logging.getLogger(__name__)


def create_validation_chain(llm: BaseChatModel, sql_validator: SQLValidator) -> Dict[str, Any]:
    """创建SQL验证链"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个SQL安全验证助手。"),
        ("human", "验证以下SQL语句：\n{sql}")
    ])
    chain = prompt | llm
    return {"chain": chain, "validator": sql_validator}


def validate_sql(sql: str, sql_validator: SQLValidator) -> Dict[str, Any]:
    """验证SQL语句"""
    result = sql_validator.validate(sql)
    if result.get("is_valid"):
        return {"is_valid": True, "sql_type": result.get("sql_type"), "warnings": result.get("warnings", [])}
    else:
        return {"is_valid": False, "errors": result.get("errors", []), "sql_type": result.get("sql_type")}
