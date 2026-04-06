# G7 修复报告

**日期**: 2026-04-04
**问题**: MD&A LLM Schema 不一致
**优先级**: 🟡 中等

---

## 问题描述

两套 Prompt Schema 并存，导致：
1. `analyze_strategy_section()` 返回 Schema B 字段（product_strategy/market_strategy等）
2. 下游期望 Schema A 字段（strategic_commitments/key_strategic_themes/risk_factors）
3. `_check_hallucination()` 持续告警 `missing_fields:strategic_commitments,...`

---

## 修复内容

### 1. prompts.py — 重写 MDA_EXTRACTION_PROMPT

- 统一引文格式为 `[战略子节第X段]`
- `key_strategic_themes` 增加四维度引导（产品/市场/技术/产能）
- `operating_highlights` 改为空数组[]而非"NONE"
- 移除 `STRATEGY_SECTION_PROMPT`（不再使用）
- 核心约束：仅提取战略子节内容，禁止扩展到其他章节

### 2. analyzer.py — `LLMAnalyzer.analyze_strategy_section()`

- 改用 `MDA_EXTRACTION_PROMPT` 替代 `STRATEGY_SECTION_PROMPT`
- `max_tokens` 提升至 8192（Schema A 输出量更大）
- 修复 `RuleBasedAnalyzer.analyze_strategy_section()` 的调用签名

### 3. analyzer.py — `_check_hallucination()`

- `operating_highlights` 不再纳入必检字段（战略子节通常无此数据）

---

## 验证结果

测试股票：招商银行(600036) 2024年报

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| LLM | deepseek-chat ✅ | deepseek-chat ✅ |
| 幻觉标记 | `missing_fields:...` ❌ | `[]` ✅ |
| strategic_commitments | 0条 | **15条** ✅ |
| key_strategic_themes | 0条 | **8条** ✅ |
| risk_factors | 0条 | **23条** ✅ |
| operating_highlights | 0条 | 0条（预期） |

---

## 风险

- `operating_highlights` 字段为0：战略子节无经营指标数据，属预期行为
- 段落引用格式：`[战略子节第X段]` 与年报其他部分 `[第X段]` 风格不同，但不影响下游解析

---

## 审查结论

✅ **G7 修复完成，通过验收**
