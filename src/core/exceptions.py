"""统一异常体系"""

from typing import Dict


class DatabaseAIError(Exception):
    """基础异常类"""

    def __init__(self, message: str, details: Dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(DatabaseAIError):
    """配置错误"""

    pass


class ValidationError(DatabaseAIError):
    """验证错误"""

    pass


class SecurityError(DatabaseAIError):
    """安全错误"""

    pass


class SQLValidationError(ValidationError):
    """SQL验证错误"""

    def __init__(self, message: str, sql: str = "", errors: list = None):
        super().__init__(
            message,
            details={"sql": sql, "errors": errors or []}
        )


class SQLInjectionError(SecurityError):
    """SQL注入攻击检测"""

    def __init__(self, message: str, sql: str = "", pattern: str = ""):
        super().__init__(
            message,
            details={"sql": sql, "pattern": pattern}
        )


class LLMError(DatabaseAIError):
    """LLM调用错误"""

    pass


class DatabaseConnectionError(DatabaseAIError):
    """数据库连接错误"""

    pass


class ExecutionError(DatabaseAIError):
    """执行错误"""

    pass


class ToolExecutionError(DatabaseAIError):
    """工具执行错误"""

    def __init__(self, message: str, tool_name: str = "", details: Dict = None):
        super().__init__(
            message,
            details={"tool_name": tool_name, **(details or {})}
        )


class WorkflowError(DatabaseAIError):
    """工作流错误"""

    pass
