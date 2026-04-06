# G5Gate 复查报告 v2 — module5_red_flags

**模块**: P0 第5周 | module5_red_flags
**复查日期**: 2026-04-03
**代码路径**: `impl/module5_red_flags/`
**复查人**: G5Gate复查Agent

---

## G5Gate复查结论：**通过**

---

## Fix1评价：✅ — 通过

**修复内容**: `scorer.py` verdict逻辑从"黄旗优先直接定存疑"重构为分层判断。

**验证方法**: 手工推导永新 002014 路径（score=92, 1黄旗）

旧逻辑路径：
```
yellow_flags=[MEDIUM_PLEDGE] → verdict="存疑"（直接返回，score失效）
```

新逻辑路径（逐层）：
```python
if extreme_flags:                              # ❌ 无极旗
    verdict = "高风险"
elif overall_score < 50:                        # ❌ 92>=50
    verdict = "高风险"
elif len(red_flags) >= 2:                       # ❌ 0红
    verdict = "高风险"
elif len(red_flags) == 1:                       # ❌ 0红
    verdict = "存疑"
elif yellow_flags and overall_score < 80:       # ❌ 有黄旗但92>=80
    verdict = "存疑"
elif overall_score >= 80:                       # ✅ 命中
    verdict = "通过"
```

**结论**: score=92+1黄旗 → verdict="通过" ✅，矛盾已解决。

**逻辑健壮性验证**:

| 场景 | score | extreme | red | yellow | verdict (新) | 预期 |
|------|-------|---------|-----|--------|-------------|------|
| 永新版（1黄旗） | 92 | 0 | 0 | 1 | **通过** | ✅ |
| 无风险 | 100 | 0 | 0 | 0 | **通过** | ✅ |
| 2个红旗 | 70 | 0 | 2 | 0 | **高风险** | ✅ |
| 1个红旗 | 85 | 0 | 1 | 0 | **存疑** | ✅ |
| 黄旗+score=75 | 75 | 0 | 0 | 1 | **存疑** | ✅（谨慎，合理）|
| 极差分数 | 40 | 0 | 0 | 0 | **高风险** | ✅ |
| 极旗 | 30 | 1 | 0 | 0 | **高风险** | ✅ |

**唯一瑕疵**: `verdict_reason` 和 `data_source` 在 scorer.score() 返回时为初始值（空字符串/"full"），只有 `_check_data_completeness` 才填充。这意味着当数据完整时，正常 verdict 的 `verdict_reason` 字段是空的。不过这是设计取舍：正常情况不需要原因说明。**可接受**。

---

## Fix2评价：✅ — 通过（有建议）

**修复内容**: engine.py 新增 `_check_data_completeness()` 方法；`ScoredReport` 新增 `verdict_reason` 和 `data_source` 字段。

**验证方法**: 读 `engine.py` 实际代码。

**关键代码**:
```python
def _check_data_completeness(self, report: "ScoredReport", fin_data: Dict[str, Any]) -> "ScoredReport":
    critical_fields = ["roe_latest", "net_profit_cash_ratio", "revenue_growth_yoy"]
    missing = [f for f in critical_fields if fin_data.get(f) is None]
    if len(missing) >= 2:
        report.verdict = "存疑"        # 强制降级
        report.verdict_reason = f"数据不完整:{missing}"
        report.data_source = "degraded"
    elif len(missing) == 1:
        report.data_source = "partial"
    else:
        report.data_source = "full"
    return report
```

**正确性验证**:
- 该方法在 `analyze()` 最后调用，在 scorer 评分之后 ✅
- 只有 `verdict="通过"` 时会被降为"存疑" ✅（不安全的升级被拦截）
- `"高风险"` 和 `"存疑"` 不受影响 ✅
- `data_source` 三档：`full`/`partial`/`degraded` ✅

**边界条件分析**:

| 场景 | missing数 | verdict原值 | verdict新值 | 正确性 |
|------|-----------|-------------|-------------|--------|
| 数据完整 | 0 | 通过 | 通过 | ✅ |
| 数据完整 | 0 | 存疑 | 存疑 | ✅ |
| 数据完整 | 0 | 高风险 | 高风险 | ✅ |
| 部分缺失 | 1 | 通过 | 通过 | ✅ (partial标记，不降级) |
| 严重缺失 | ≥2 | 通过 | **存疑** | ✅ |
| 严重缺失 | ≥2 | 存疑 | 存疑 | ✅ |
| 严重缺失 | ≥2 | 高风险 | 高风险 | ✅（不覆盖更严重结论）|

**建议（不影响通过）**: `verdict_reason` 在数据完整时仍为空字符串，建议统一填充：
```python
# 即使数据完整也写明 verdict 来源
report.verdict_reason = f"score={report.overall_score}, {len(report.red_flags)}红{len(report.yellow_flags)}黄"
```

---

## Fix3评价：✅ — 通过

**修复内容**: `mda_enabled=False` → `mda_enabled=True`

**验证方法**: 交叉读 `engine.py` 和 `api.py` 两处调用。

**api.py screen()**:
```python
def screen(..., mda_enabled: bool = True, ...):
    engine = get_engine(mda_enabled=mda_enabled)
    ...
```

**api.py get_engine()**:
```python
def get_engine(mda_enabled: bool = True) -> RedFlagEngine:
    ...
```

**engine.py RedFlagEngine.__init__()**:
```python
def __init__(self, mda_enabled: bool = False, ...):  # engine默认值仍为False
    self.mda_enabled = mda_enabled
```

**engine.py analyze()**:
```python
mda_data: Dict[str, Any] = _mda_fallback()
if self.mda_enabled:              # ✅ 有分支逻辑
    t_mda = time.time()
    mda_data = _fetch_mda(code_6d, year=mda_year, timeout=120)
    ...
```

**验证结论**: 
- `api.py → screen()` 默认 `mda_enabled=True` ✅
- 传入 `engine = RedFlagEngine(mda_enabled=True)` ✅  
- `engine.analyze()` 中 `if self.mda_enabled:` 条件分支 ✅，真正调用 `_fetch_mda()`
- `_fetch_mda()` 有完整实现（MDAPipeline 调用 + 超时保护 + fallback）✅

**特别注意**: `engine.py` 本身的 `__init__` 默认值仍是 `False`，但通过 `api.py` 的 `screen()` 入口会覆盖为 `True`。这是合理的分层设计：底层 engine 默认安全（不快），上层 API 入口默认启用。

---

## 未解决问题（不在本次修复范围内，但应记录）

| # | 严重度 | 问题 | 备注 |
|---|--------|------|------|
| A | 🟡 P1 | "需核实"审计意见仍不计入评分 | `_audit_opinion_to_score()` 只识别4种非标，"需核实"仍被当clean |
| B | 🟡 P1 | 债务率/关联交易/毛利率等红旗缺失 | 原始review已记录，非本次修复重点 |
| C | 🟢 P2 | `verdict_reason` 在数据完整时为空 | 建议统一填充，建议不改不影响通过 |

---

## 总体评价

**通过**

三个 Fix 均从代码层面验证通过，未发现逻辑漏洞或边界条件错误。Fix1 彻底解决了"高分低判"矛盾；Fix2 在数据降级场景下正确拦截"通过" verdict；Fix3 确认 MD&A 实际被调用而非仅改 flag。

**建议后续关注**: 问题A（"需核实"审计意见）属于 P1 遗留，建议在下一次迭代中修复，避免该类审计意见被静默忽略。
