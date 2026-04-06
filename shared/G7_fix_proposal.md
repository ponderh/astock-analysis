# G7Gate Fix Proposal — MD&A LLM Schema对齐修复

**审查人**: 评估Agent（Critic）
**日期**: 2026-04-04
**问题级别**: 🟡 中等（影响MD&A战略分析数据完整性，不阻塞其他模块）

---

## 一、问题描述

### 根因：两套Prompt Schema不一致

`prompts.py` 定义了两套不同的 JSON Schema：

**Schema A - `MDA_EXTRACTION_PROMPT`**（被期望的下游schema）：
```json
{
    "strategic_commitments": [...],   // 数组
    "key_strategic_themes": [...],   // 数组
    "risk_factors": [...],           // 数组
    "operating_highlights": [...],    // 数组
    ...
}
```

**Schema B - `STRATEGY_SECTION_PROMPT`**（pipeline实际调用的）：
```json
{
    "product_strategy": "...",        // 字符串
    "market_strategy": "...",
    "technology_strategy": "...",
    "capacity_strategy": "...",
    "quantitative_targets": [...],
    "time_commitments": [...],
    "confidence_level": "..."
}
```

**调用链**：
```
pipeline.py: analyze_strategy_section(strategy_text)
    → LLMAnalyzer.analyze(...)
    → STRATEGY_SECTION_PROMPT (Schema B)
    → 返回 {technology_strategy: "...", ...}
    → downstream expects {strategic_commitments: [], ...} ← Schema A
    → hallucination_flags: missing_fields:strategic_commitments,...
```

**影响**：LLM分析结果字段与下游期望不一致， hallucination_flags 持续告警。

---

## 二、修复方案

### 推荐方案：统一Schema，将STRATEGY_SECTION_PROMPT替换为MDA_EXTRACTION_PROMPT

**理由**：
1. `MDA_EXTRACTION_PROMPT` schema 更完整（包含 commitments/themes/risks/highlights）
2. 战略子节的核心内容（战略承诺、战略主题、风险因素）与 Schema A 完全对应
3. 避免两套schema并存导致的混乱

### 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `impl/module6_mda/prompts.py` | 将 `STRATEGY_SECTION_PROMPT` 替换为 `MDA_EXTRACTION_PROMPT` |
| `impl/module6_mda/analyzer.py` | `analyze_strategy_section()` 改调用 `MDA_EXTRACTION_PROMPT` |
| `impl/module6_mda/pipeline.py` | 无需修改（已正确调用 `analyze_strategy_section`） |

### 验证标准

修复后，招商银行2024年报：
- [ ] LLM幻觉告警消失（`missing_fields:strategic_commitments,...` 不出现）
- [ ] `strategic_analysis.structured_data` 包含 `strategic_commitments`、`key_strategic_themes`、`risk_factors`
- [ ] `operating_highlights` 有数据（非空）
- [ ] 单元测试通过

---

## 三、风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 更换prompt后LLM对特定格式输出不稳定 | 低 | 中 | 用招商银行2024实测验证 |
| `MDA_EXTRACTION_PROMPT`更长，超token限制 | 低 | 中 | strategy_text限制5000字，已做截断 |
| 规则引擎fallback与新schema不兼容 | 低 | 低 | 规则引擎不依赖schema，是regex匹配 |

---

## 四、实施步骤

1. **修改 `analyzer.py`**: `analyze_strategy_section()` 改用 `MDA_EXTRACTION_PROMPT`
2. **修改 `prompts.py`**: `STRATEGY_SECTION_PROMPT` 改为直接引用 `MDA_EXTRACTION_PROMPT`（或删除重复定义）
3. **实测验证**: 招商银行(600036) 2024年报端到端运行
4. **回归验证**: 永新股份(002014) 2020-2024五年历史回归测试

---

待评估Agent审查。
