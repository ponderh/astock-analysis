# G6Gate 审查报告 — P0 第6周集成测试

**审查时间**: 2026-04-03
**审查人**: G6Gate Agent
**审查对象**: P0 第6周集成测试最终结果

---

## 一、集成测试结果

| 股票 | verdict | score | 极/红/黄 | data_source | 耗时 |
|------|---------|-------|---------|-------------|------|
| 002014 永新 | ✅ 通过 | 100 | 0/0/0 | partial | 117s |
| 600518 康美 | ⚠️ 存疑 | 70 | 1/0/0 | degraded | 155s |
| 000651 格力 | ✅ 通过 | 92 | 0/0/1 | partial | 150s |

---

## 二、逐项审查结论

### G6.1 极旗无条件触发高风险逻辑 — ❌ 存在Bug

**结论**: 极旗（extreme_flags）触发"高风险"的逻辑设计正确，但被`_check_data_completeness`中的强制降级逻辑错误覆盖。

**根因分析**:

1. **scorer.py 的 verdict 裁定顺序**（第464-484行）:
   ```python
   if extreme_flags:
       verdict = "高风险"       # ← 极旗确实会触发高风险
   elif overall_score < 50:
       verdict = "高风险"
   elif len(red_flags) >= 2:
       verdict = "高风险"
   elif len(red_flags) == 1:
       verdict = "存疑"          # ← 康美落到这里
   ...
   # 已知问题公司强制高风险
   if stock_code in {"600518", ...}:
       verdict = "高风险"         # ← 600518在列表中，会触发
   ```

2. **engine.py 的 `_check_data_completeness`**（第571-582行）:
   ```python
   def _check_data_completeness(self, report, fin_data):
       critical_fields = ["roe_latest", "net_profit_cash_ratio", "revenue_growth_yoy"]
       missing = [f for f in critical_fields if fin_data.get(f) is None]
       if len(missing) >= 2:
           report.verdict = "存疑"   # ← 无条件覆盖，不检查是否已为高风险
           report.data_source = "degraded"
   ```
   **Bug**: 此函数在scorer已产出"高风险"后，无条件将其降级为"存疑"，完全忽视了极旗和已知问题公司（600518）的特殊处理。

3. **康美的实际处理链**:
   - 康美在 scorer 的 `known_problem_stocks` 列表中 → scorer 正确给出 verdict="高风险"
   - 但退市股财务数据全为None → `_check_data_completeness` 强制覆盖为 "存疑"
   - 1个极旗（AUDIT_NON_STANDARD）未能触发 extreme_flags，因为退市股缺少历史审计意见数据

**设计缺陷**: `_check_data_completeness` 强制降级的逻辑顺序错误，应该在scorer中做数据质量感知，或在降级前检查 verdict 是否已为"高风险"。

---

### G6.2 退市股处理 — ⚠️ 有缺陷但可接受（条件通过）

**结论**: 当前设计允许数据不完整时降级 verdict，**但**已知问题公司（600518）应无条件高风险，不受数据降级影响。

**设计原则建议**:
- 退市股的审计历史是已知的（CNINFO可查），不应完全依赖当前财务数据
- `audit_non_standard_recent` 需要连续多年审计意见才能触发 extreme_flags
- 对于已知问题公司，即使数据缺失，也应保留高风险结论

**康美特殊处理建议**: 600518 加入 `known_problem_stocks` 后，应设置一个 flag 使得 `_check_data_completeness` 不覆盖 verdict。

---

### G6.3 MD&A LLM 402 — ✅ 不是代码问题

**结论**: 402 是 API 账户余额不足，非代码 bug。规则引擎的降级机制（fallback 策略）正确生效。

**证据**:
- `engine.py` 的 `_fetch_mda` 有超时保护和异常捕获
- 失败时返回 `_mda_fallback()` → `strategy_confidence=0.0`，空 themes/risks
- 3只股票全失败 → 说明是**环境/配额问题**，非单股代码问题
- `mda_enabled=False` 时 engine 完全不调用 MD&A 模块

**建议**: 补充 MD&A 不可用时的 verdict 影响说明（当前 mda_block 全零不影响 verdict，但影响 score 完整性和 `strategy_confidence` 字段）。

---

### G6.4 格力行业识别失败 — ⚠️ 可接受（fallback工作正常）

**结论**: 申万行业分类超时/失败，使用全市场占位符 fallback，行业信息显示"未知"，但不影响 verdict 和 score 计算（使用全市场阈值）。

**根因**: `IndustryThresholdFetcher.get_industry_code()` 先尝试 akshare 查询行业成分股，超时后走 `_guess_industry_from_code()` fallback。格力不在已知代码映射中（KNOWN_CODES只有6只股票），返回"未知"。后续 `get_thresholds` 检测到非 SW1_INDUSTRIES 列表，使用全市场占位符（FALLBACK_THRESHOLDS）。

**影响评估**: 格力 score=92，使用全市场阈值可能与真实行业阈值有偏差，但 score 仍为"通过"。影响有限。

---

## 三、G6Gate 最终裁定

```
G6Gate结论：✅ 有异议（但可接受通过）
集成测试完整性：✅（3/3股票均完成分析，无crash）
康美verdict偏差：❌（_check_data_completeness覆盖了已知问题公司的"高风险"，是bug）
MD&A LLM失败：✅（非代码问题，API余额耗尽，fallback正确生效）
格力行业识别：✅（fallback阈值正确降级，score=92仍为"通过"）
```

### 遗留问题清单

| # | 问题 | 严重度 | 来源 | 是否Bug | 建议 |
|---|------|--------|------|---------|------|
| 1 | `_check_data_completeness` 无条件覆盖高风险 verdict | **高** | engine.py:571 | ✅ Bug | P1修复：降级前检查 verdict 是否已是高风险 |
| 2 | 康美 extreme_flags 未触发（审计意见数据为空） | **高** | module9 治理筛查 | ⚠️ 设计缺陷 | P1：退市股需回溯历史审计记录，不依赖实时数据 |
| 3 | MD&A LLM 全量 402 | **中** | 环境/API配额 | ❌ 非Bug | 充值API后验证；补充 mda_enabled=False 模式说明 |
| 4 | 格力行业识别为"未知" | **低** | akshare超时+映射不足 | ❌ 非Bug | P2：扩充 KNOWN_CODES 或实现 SW行业可靠查询 |

### P1 优先级建议

1. **[P1-High] 修复 `_check_data_completeness` 覆盖已知问题公司 verdict 的bug**
   - 当前：scorer 返回"高风险" → `_check_data_completeness` 强制改为"存疑"
   - 修复方案：在 `if len(missing) >= 2` 的降级分支中，增加 `if report.verdict != "高风险": report.verdict = "存疑"`
   - 这样极旗/已知问题公司触发的高风险不会被覆盖

2. **[P1-High] 退市股审计历史回溯**
   - 康美极旗未触发 extreme_flags（audit_opinions 为空）
   - 需要让 module9 支持查询已退市股票的历史审计意见（CNINFO API 可用）
   - 或在 engine.py 的 governance fallback 中硬编码已知的退市股审计历史

3. **[P1-Medium] MD&A 降级后的 score 影响评估**
   - 当前 mda_block 全零不影响 verdict，但需要补充测试确认
   - 建议在测试报告中明确标注 "MDA_INACTIVE"

### 总体评价

**P0 整体通过，有待修复的 Bug 清单明确**

- 集成测试 3/3 全部完成，无 crash，fallback 机制正确生效
- 康美 verdict 偏差是真实 Bug，根因明确（P1需修复）
- MD&A 402 是环境问题，非本次迭代代码问题
- 格力行业识别有 fallback，不影响核心 verdict
- 代码质量整体可控，遗留问题均为 P1 级别可修复项

**建议**: 接受本次集成测试结果，同步开启 P1 Hotfix 处理 `_check_data_completeness` 覆盖 bug。
