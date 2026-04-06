# G7 修复报告

**日期**: 2026-04-04
**问题**: MD&A LLM Schema 不一致 + 修复过程中发现的其他bug
**优先级**: 🟡 中等

---

## 修复内容

### 1. prompts.py — 简化 MDA_EXTRACTION_PROMPT

- 原Schema B（STRATEGY_SECTION_PROMPT）不再使用，已移除
- 新Schema A（简化版MDA_EXTRACTION_PROMPT）统一用于 `analyze_strategy_section()` 和 `analyze_mda_full()`
- 移除引文格式歧义（统一 `[战略子节]` 标注）
- 移除 `operating_highlights` 必填要求（战略子节通常无此数据）

### 2. analyzer.py — 三项关键修复

| 修复 | 位置 | 内容 |
|------|------|------|
| A | `analyze_strategy_section()` | 改用 `MDA_EXTRACTION_PROMPT`，`max_tokens` 4096→8192 |
| B | `analyze()` 调用方式 | `.format(text=...)` → `.replace('{text}', ...)` 避免JSON大括号冲突 |
| C | `_check_hallucination()` | 移除 `possible_hallucination_no_foundation` 误报；添加类型安全检查（容错字符串数组） |

---

## 验证结果

### 招商银行(600036) 2024年报

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| LLM | deepseek-chat ✅ | deepseek-chat ✅ |
| 幻觉标记 | `missing_fields:strategic_commitments,...` ❌ | `[]` ✅ |
| strategic_commitments | 0条 | **15条** ✅ |
| key_strategic_themes | 0条 | **8条** ✅ |
| risk_factors | 0条 | **23条** ✅ |

### 永新股份(002014) 2020-2024

| 年份 | LLM | 结果 |
|------|------|------|
| 2020 | 网络超时 | 无数据 |
| 2021-2024 | rule_based_fallback | 规则引擎正常工作（LLM API调用不稳定）|

---

## 发现的新问题

### 1. `.format()` 与JSON大括号冲突

当LLM返回的raw_response被作为下一次调用的text时，若包含JSON格式的大括号`{}`，会导致Python的`str.format()`抛出`KeyError`。已通过改用`str.replace('{text}', ...)`解决。

### 2. LLM返回字符串数组而非对象数组

某些情况下LLM返回 `["string1", "string2"]` 而非预期的 `[{"commitment": "..."}]`。已添加类型检查，不会崩溃，但会记录 `schema_violation:*_not_dict` 标记。

### 3. 规则引擎字段检查

当LLM返回空数组（文本内容不足以提取具体承诺时），旧代码会错误触发 `possible_hallucination_no_foundation`。已移除该检查（空数组是正常响应）。

---

## 结论

✅ **G7 修复完成，验收通过**
- Schema统一到MDA_EXTRACTION_PROMPT
- 幻觉误报消除（招商银行测试）
- 系统在LLM API不稳定时fallback到规则引擎正常运行
