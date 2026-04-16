"""SQL生成链 - LCEL实现"""
import json
import logging
import re
from typing import Dict, Any, Optional, List

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

from ..schema.manager import SchemaManager
from ..prompts.manager import PromptManager
from ..tools.registry import create_database_tools
from ..security.validator import SQLValidator
from ..database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


def create_sql_generation_chain(llm: BaseChatModel, schema_manager: SchemaManager, prompt_manager: PromptManager, sql_validator: SQLValidator, db_connection: Optional[DatabaseConnection] = None, max_iterations: int = 10) -> Dict[str, Any]:
    """创建SQL生成链"""
    system_prompt = prompt_manager.get_agent_system_prompt()
    tools = create_database_tools(db_connection=db_connection, schema_manager=schema_manager, sql_validator=sql_validator, include_validate=False)
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt),
        HumanMessagePromptTemplate.from_template("{query}")
    ])
    llm_with_tools = llm.bind_tools(tools)
    return {"llm": llm, "llm_with_tools": llm_with_tools, "prompt": prompt, "tools": tools, "max_iterations": max_iterations}


def extract_sql_from_response(response: str) -> List[Dict[str, str]]:
    """从LLM响应中提取SQL列表"""
    sql_list = []
    try:
        data = json.loads(response)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "sql" in item:
                    sql = item["sql"]
                    sql_type = item.get("type") or _detect_sql_type(sql)
                    if sql:
                        sql_list.append({"type": sql_type, "sql": sql})
            if sql_list:
                return sql_list
        elif isinstance(data, dict) and "sql" in data:
            sql = data["sql"]
            sql_type = data.get("type") or _detect_sql_type(sql)
            if sql:
                return [{"type": sql_type, "sql": sql}]
    except json.JSONDecodeError:
        pass

    json_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    for json_str in re.findall(json_block_pattern, response, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(json_str.strip())
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "sql" in item:
                        sql = item["sql"]
                        sql_type = item.get("type") or _detect_sql_type(sql)
                        if sql:
                            sql_list.append({"type": sql_type, "sql": sql})
                if sql_list:
                    return sql_list
        except json.JSONDecodeError:
            continue

    sql_block_pattern = r'```(?:sql)?\s*\n?(.*?)\n?```'
    for sql in re.findall(sql_block_pattern, response, re.DOTALL | re.IGNORECASE):
        sql = sql.strip()
        if sql:
            sql_type = _detect_sql_type(sql)
            sql_list.append({"type": sql_type, "sql": sql})

    if sql_list:
        return sql_list

    sql_pattern = r'([A-Za-z_]+)\s+.+?(?:;|$)'
    for match in re.findall(sql_pattern, response, re.IGNORECASE | re.DOTALL):
        sql = match.strip()
        if sql:
            sql_type = _detect_sql_type(sql)
            sql_list.append({"type": sql_type, "sql": sql})

    return sql_list


def _detect_sql_type(sql: str) -> str:
    """检测SQL语句类型"""
    match = re.match(r'^\s*(\w+)', sql.strip())
    return match.group(1).lower() if match else 'unknown'
