"""AI客户端工厂 - 已废弃，请使用 src.llm.factory.LLMFactory"""
import logging
from typing import Optional, Any

from ..core.config.settings import Settings

logger = logging.getLogger(__name__)


def get_ai_client(settings: Settings) -> Optional[Any]:
    """获取AI客户端实例 - 已废弃，请使用 LLMFactory"""
    from ..llm.factory import LLMFactory

    try:
        factory = LLMFactory(settings)
        return factory.create_llm()
    except Exception as e:
        logger.warning(f"创建LLM客户端失败: {e}")
        return None
