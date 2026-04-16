"""DB-AI-Server 主入口 - LangChain v1.0 规范实现

基于LangChain规范的AI数据库SQL生成服务器
"""
import asyncio
import logging
import sys
from pathlib import Path

# 添加src到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcp.server import create_mcp_server, setup_logging


async def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("DB-AI-Server v7.0 - LangChain v1.0 规范实现")
    logger.info("=" * 60)

    server = create_mcp_server()
    await server.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("服务器已停止")
    except Exception as e:
        logging.error(f"服务器错误: {e}")
        sys.exit(1)
