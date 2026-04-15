"""共享类型定义"""
from typing import Dict, Any, List, Optional, Literal, TypedDict, Union
from enum import Enum


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SQLType(str, Enum):
    """SQL类型"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    UNKNOWN = "UNKNOWN"


class ValidationResult(TypedDict):
    """验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    sql_type: Optional[str]


class SQLGenerationResult(TypedDict):
    """SQL生成结果"""
    sql: str
    sql_type: str
    affected_tables: List[str]
    estimated_rows: int
    risk_level: str
    explanation: str
    require_confirmation: bool
    warnings: List[str]
    suggestions: List[str]
    follow_up_sql: Optional[str]
    requires_verification: bool


class ExecutionResult(TypedDict):
    """执行结果"""
    success: bool
    rows: List[Dict[str, Any]]
    affected_rows: int
    columns: List[str]
    column_comments: Dict[str, str]
    error: Optional[str]


class AgentState(TypedDict):
    """Agent状态"""
    query: str
    user_context: Optional[Dict[str, Any]]
    sql: Optional[str]
    sql_type: Optional[str]
    execution_result: Optional[ExecutionResult]
    validation_result: Optional[ValidationResult]
    risk_level: Optional[str]
    response: Optional[str]
    error: Optional[str]
    steps: List[Dict[str, Any]]
    finished: bool


class ToolCall(TypedDict):
    """工具调用"""
    name: str
    arguments: Dict[str, Any]
    result: Optional[str]
    error: Optional[str]


class WorkflowResult(TypedDict):
    """工作流结果"""
    success: bool
    query: str
    response: Optional[str]
    intermediate_steps: List[Dict[str, Any]]
    data: Optional[Dict[str, Any]]
    error: Optional[str]
