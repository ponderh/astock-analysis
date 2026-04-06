"""
MD&A LLM分析Prompt模板
三层幻觉保障: 约束性Prompt + Schema校验 + 后处理一致性检查
"""

# ============================================================================
# 统一Schema：MDA_EXTRACTION_PROMPT
# 用于: analyze_strategy_section() + analyze_mda_full()
# 适用: 战略子节 + 完整MD&A章节
# ============================================================================
MDA_EXTRACTION_PROMPT = """[角色] 你是一个精确的信息提取专家。
[任务] 从年报战略文本中提取结构化JSON。

[要求]
- 仅提取文本中明确包含的内容，禁止推断
- 数字必须照抄原文，禁止四舍五入
- 输出严格JSON格式，不要任何额外说明

[JSON格式 - 必须严格遵循]
{
    "strategic_commitments": [
        {
            "commitment": "具体战略承诺",
            "time_horizon": "短期/中期/长期/NONE",
            "quantitative_target": "量化目标或NONE",
            "source_quote": "[战略子节]引文"
        }
    ],
    "key_strategic_themes": [
        {
            "theme": "战略主题",
            "description": "主题描述（产品/市场/技术/产能维度）",
            "evidence_quote": "[战略子节]引文"
        }
    ],
    "risk_factors": [
        {
            "risk": "风险描述",
            "mitigation": "应对措施或NONE",
            "source_quote": "[战略子节]引文"
        }
    ],
    "operating_highlights": []
}

[特殊处理]
- 无法提取：输出[]（数组）或"NONE"（字符串），禁止省略字段
- 禁止模糊词："大约"、"约"、"基本"、"可能"

[待分析文本]
{text}

[JSON输出]
"""

# ============================================================================
# 质量校验Prompt
# ============================================================================
HALLUCINATION_CHECK_PROMPT = """[角色] 你是一个严格的信息审计员。
[任务] 检查以下LLM提取结果是否存在幻觉。

原始文本摘要（供参考）:
{original_summary}

LLM提取结果:
{llm_response}

[检查项目]
1. 数字核对：提取的数字是否与原文一致？
2. 引文核对：引文内容是否能在原文中找到？
3. 推断检测：是否有无中生有的推断？

[输出格式]
{{
    "has_hallucination": true/false,
    "hallucination_details": ["问题1", "问题2或NONE"],
    "confidence": "high/medium/low"
}}
"""

# ============================================================================
# 章节定位评估Prompt
# ============================================================================
LOCATION_ASSESSMENT_PROMPT = """[角色] 你是一个专业的年报结构分析师。
[任务] 评估以下MD&A章节提取是否完整。

[章节标题] {section_title}
[章节长度] {char_count} 字符
[子节数量] {subsection_count}
[关键词覆盖] {keyword_coverage}

[输出]
{{
    "is_complete": true/false,
    "missing_sections": ["缺失的子节1", "缺失的子节2或NONE"],
    "confidence": "high/medium/low"
}}
"""
