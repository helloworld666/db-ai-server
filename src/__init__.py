"""DB-AI-Server - LangChain v1.0 规范实现

基于LangChain规范的AI数据库SQL生成服务器
核心原则：
1. 所有配置从JSON文件读取，禁止硬编码
2. 所有提示词从配置文件读取，禁止硬编码
3. 工具调用完全由LLM自主决定
4. 数据库Schema从配置文件动态加载
5. 使用LangChain v1.0 LCEL标准API
"""

__version__ = "7.0.0"
__langchain_version__ = "1.0"
