"""LangChain工具注册中心 - 统一管理所有工具"""
import logging
from typing import Dict, List, Optional, Any, Callable
from langchain_core.tools import BaseTool, StructuredTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """LangChain工具注册中心 - 单例模式"""

    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, BaseTool] = {}
    _tool_factories: Dict[str, Callable] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, name: str, tool: BaseTool):
        """注册工具"""
        self._tools[name] = tool
        logger.debug(f"注册工具: {name}")

    def register_factory(self, name: str, factory: Callable):
        """注册工具工厂"""
        self._tool_factories[name] = factory
        logger.debug(f"注册工具工厂: {name}")

    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)

    def get_all(self) -> List[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())

    def get_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())

    def has(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools

    def unregister(self, name: str):
        """取消注册工具"""
        if name in self._tools:
            del self._tools[name]
            logger.debug(f"取消注册工具: {name}")

    def clear(self):
        """清空所有工具"""
        self._tools.clear()
        logger.debug("已清空所有工具")

    def create_tools(self, **dependencies) -> List[BaseTool]:
        """使用工厂创建所有工具"""
        tools = []
        for name, factory in self._tool_factories.items():
            try:
                tool = factory(**dependencies)
                self.register(name, tool)
                tools.append(tool)
                logger.debug(f"创建并注册工具: {name}")
            except Exception as e:
                logger.error(f"创建工具 {name} 失败: {e}")

        return tools

    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """按类别获取工具"""
        tools = []
        prefix = f"{category}_"
        for name, tool in self._tools.items():
            if name.startswith(prefix):
                tools.append(tool)
        return tools


# 全局实例
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取工具注册中心实例"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(name: str):
    """工具注册装饰器"""
    def decorator(func_or_class):
        registry = get_tool_registry()
        if isinstance(func_or_class, type) and issubclass(func_or_class, BaseTool):
            # 类形式的工具
            registry.register(name, func_or_class())
        else:
            # 函数形式的工具，使用StructuredTool包装
            tool = StructuredTool.from_function(func_or_class)
            registry.register(name, tool)
        return func_or_class
    return decorator
