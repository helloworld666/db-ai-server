"""提示词管理 - 从配置文件动态加载"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class FieldMappingGenerator:
    """字段映射生成器 - 从Schema自动生成转换规则"""

    @staticmethod
    def generate_display_rules(schema_manager) -> str:
        """从Schema自动生成所有显示映射规则（不限于enable字段）"""
        rules = []

        # 遍历所有表
        for table_name in schema_manager.get_all_table_names():
            mappings = schema_manager.get_table_display_mappings(table_name)

            for col_name, mapping in mappings.items():
                if mapping.get("display_mapping"):
                    display_map = mapping["display_mapping"]
                    output_name = mapping.get("output_name", col_name)

                    # 生成CASE WHEN语句
                    cases = []
                    for val, label in display_map.items():
                        cases.append(f"WHEN {col_name} = {val} THEN '{label}'")

                    sql_fragment = f"CASE {' '.join(cases)} END AS `{output_name}`"
                    rules.append(f"- {table_name}.{col_name}: 使用 {sql_fragment}")

        return "\n".join(rules) if rules else ""

    @staticmethod
    def get_select_column_hints(schema_manager, table_name: str) -> List[str]:
        """获取SELECT时需要的列转换提示"""
        hints = []
        mappings = schema_manager.get_table_display_mappings(table_name)

        for col_name, mapping in mappings.items():
            if mapping.get("display_mapping"):
                output_name = mapping.get("output_name", col_name)
                display_map = mapping["display_mapping"]

                # 生成SQL片段
                cases = " ".join([f"WHEN {col_name} = '{k}' THEN '{v}'" for k, v in display_map.items()])
                hints.append(f"CASE {col_name} {cases} END AS `{output_name}`")

        return hints


class PromptManager:
    """提示词管理器 - 所有提示词从配置文件读取"""

    def __init__(self, config_path: str = "config"):
        """
        初始化提示词管理器

        Args:
            config_path: 配置文件目录路径
        """
        self.config_path = Path(config_path)
        self._prompts_cache: Optional[Dict[str, Any]] = None
        self._load_prompts()

    def _load_prompts(self):
        """从配置文件加载提示词"""
        prompts_file = self.config_path / "prompts.json"
        if prompts_file.exists():
            with open(prompts_file, "r", encoding="utf-8") as f:
                self._prompts_cache = json.load(f)
            logger.info("已加载提示词配置")
        else:
            self._prompts_cache = {}
            logger.warning(f"提示词配置文件不存在: {prompts_file}")

    def reload(self):
        """重新加载提示词"""
        self._prompts_cache = None
        self._load_prompts()

    def get_system_prompt(self) -> str:
        """获取系统提示词（包含示例）"""
        system_prompt = self._prompts_cache.get('system_prompt', '')
        
        # 添加示例部分
        examples = self._prompts_cache.get('examples', [])
        if examples:
            example_text = "\n\n【Usage Examples】\n"
            for i, example in enumerate(examples, 1):
                example_text += f"\n{i}. User: {example.get('user', '')}\n"
                
                # assistant字段现在是JSON字符串
                assistant_response = example.get('assistant', '')
                if assistant_response:
                    example_text += f"   Assistant Response: {assistant_response}\n"
                
                if example.get('description'):
                    example_text += f"   （描述: {example['description']}）\n"
        
            system_prompt += example_text
        
        return system_prompt

    def get_instructions(self) -> Dict[str, Any]:
        """获取指令配置"""
        return self._prompts_cache.get('instructions', {})

    def get_core_rules(self) -> list:
        """获取核心规则"""
        return self.get_instructions().get('core_rules', [])

    def get_select_rules(self) -> list:
        """获取查询规则"""
        return self.get_instructions().get('select_rules', [])

    def get_performance_rules(self) -> list:
        """获取性能规则"""
        return self.get_instructions().get('performance_rules', [])

    def get_output_constraints(self) -> list:
        """获取输出约束"""
        return self.get_instructions().get('output_constraints', [])

    def get_operation_principles(self) -> list:
        """获取操作原则"""
        return self.get_instructions().get('operation_principles', [])

    def get_output_template(self) -> Dict[str, Any]:
        """获取输出模板"""
        return self._prompts_cache.get('output_format', {}).get('template', {})

    def get_business_rules(self) -> Dict[str, str]:
        """获取业务规则"""
        return self._prompts_cache.get('business_rules', {})

    def get_field_mappings(self) -> Dict[str, str]:
        """获取字段映射"""
        return self._prompts_cache.get('field_mappings', {})

    def get_risk_assessment(self) -> Dict[str, str]:
        """获取风险评估规则"""
        return self._prompts_cache.get('risk_assessment', {})

    def get_display_mapping_section(self) -> Dict[str, str]:
        """获取字段显示映射配置节"""
        return self._prompts_cache.get('display_mapping_section', {})

    def get_section_titles(self) -> Dict[str, str]:
        """获取所有章节标题配置"""
        return self._prompts_cache.get('section_titles', {})

    def get_section_title(self, key: str, default: str = "") -> str:
        """获取指定章节标题"""
        titles = self.get_section_titles()
        return titles.get(key, default)

    def get_sql_generation_prompt(self, database_structure: str, query: str, business_rules: str = "") -> str:
        """构建SQL生成提示词"""
        template = self._prompts_cache.get('sql_generation', '')

        if template:
            try:
                return template.format(
                    database_structure=database_structure,
                    query=query,
                    business_rules=business_rules
                )
            except KeyError:
                # 如果模板缺少某些参数
                return template.format(
                    database_structure=database_structure,
                    query=query
                )

        # 如果没有模板，构建默认提示词
        prompt_parts = []

        # 系统提示词
        system_prompt = self.get_system_prompt()
        if system_prompt:
            prompt_parts.append(system_prompt)

        # 核心规则
        core_rules = self.get_core_rules()
        if core_rules:
            core_rules_title = self.get_section_title("core_rules", "核心规则")
            prompt_parts.append(f"\n{core_rules_title}:")
            for rule in core_rules:
                prompt_parts.append(f"- {rule}")

        # 操作原则
        operation_principles = self.get_operation_principles()
        if operation_principles:
            operation_principles_title = self.get_section_title("operation_principles", "操作原则")
            prompt_parts.append(f"\n{operation_principles_title}:")
            for principle in operation_principles:
                prompt_parts.append(f"- {principle}")

        # 业务规则
        if business_rules:
            business_rules_title = self.get_section_title("business_rules", "业务规则")
            prompt_parts.append(f"\n{business_rules_title}:\n{business_rules}")

        # 表结构
        db_structure_title = self.get_section_title("database_structure", "数据库结构")
        prompt_parts.append(f"\n{db_structure_title}:\n{database_structure}")

        # 输出格式
        output_format_title = self.get_section_title("output_format", "输出格式")
        prompt_parts.append(f"\n{output_format_title}:")
        template_fields = self.get_output_template()
        prompt_parts.append(f"Return JSON containing the following fields: {', '.join(template_fields.keys())}")

        # 用户查询
        user_query_title = self.get_section_title("user_query", "User Query")
        prompt_parts.append(f"\n{user_query_title}: {query}")

        return "\n".join(prompt_parts)

    def build_agent_system_prompt(self, schema_summary: str = "", schema_manager=None) -> str:
        """
        构建Agent系统提示词

        Args:
            schema_summary: 表结构摘要
            schema_manager: Schema管理器实例，用于自动生成字段映射规则
        """
        prompt_parts = []

        # 基础系统提示词
        system_prompt = self.get_system_prompt()
        if system_prompt:
            prompt_parts.append(system_prompt)

        # 添加指令（使用配置中的标题）
        instructions = self.get_instructions()
        if instructions:
            for key, value in instructions.items():
                if isinstance(value, list) and value:
                    section_title = self.get_section_title(key, key.replace('_', ' ').title())
                    prompt_parts.append(f"\n{section_title}:")
                    for item in value:
                        prompt_parts.append(f"- {item}")

        # 添加业务规则
        business_rules = self.get_business_rules()
        if business_rules:
            section_title = self.get_section_title("business_rules", "业务规则")
            prompt_parts.append(f"\n{section_title}:")
            for table, rule in business_rules.items():
                prompt_parts.append(f"- {table}: {rule}")

        # 自动生成字段映射规则（从Schema配置和提示词配置）
        if schema_manager:
            auto_rules = FieldMappingGenerator.generate_display_rules(schema_manager)
            if auto_rules:
                mapping_config = self.get_display_mapping_section()
                prompt_parts.append(f"\n{mapping_config.get('title', '字段显示映射')}:")
                prompt_parts.append(mapping_config.get('description', '查询时使用CASE WHEN转换'))
                prompt_parts.append(auto_rules)
                prompt_parts.append(f"\n{mapping_config.get('example_prefix', '示例：')} {mapping_config.get('example_sql', '')}")

        # 添加配置文件中的字段映射（作为补充）
        field_mappings = self.get_field_mappings()
        if field_mappings:
            default_behavior = field_mappings.pop("default_behavior", None)
            other_mapping_title = self.get_section_title("other_field_mappings", "其他字段映射规则")
            prompt_parts.append(f"\n{other_mapping_title}:")
            for key, mapping in field_mappings.items():
                if key != "default_behavior":
                    prompt_parts.append(f"- {key}: {mapping}")
            if default_behavior:
                default_behavior_title = self.get_section_title("default_behavior", "默认行为")
                prompt_parts.append(f"- {default_behavior_title}: {default_behavior}")

        # 表结构摘要（如果提供）
        if schema_summary:
            tables_title = self.get_section_title("available_tables", "可用数据库表")
            prompt_parts.append(f"\n{tables_title}:\n{schema_summary}")

        return "\n".join(prompt_parts)
