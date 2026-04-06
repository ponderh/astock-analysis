# G2 Gate Review — 历史数据管道 & 行业阈值库

评估结论：有异议（条件通过，需修复3个问题）
Gate编号：G2
审查时间：2026-04-03 13:40 CST

module2审查：有异议 — 数据流可跑通，但存在关键数据溯源问题和一处代码bug
industry_thresholds审查：有异议 — API可用且组合逻辑正确，但阈值全为占位符、三级降级未真正实现

---

## 问题列表

### P1（必须修复）

**1. [module2] HDF5净现比数据溯源错误，导致0.68与专家值0.98差异无法解释**
- 严重程度：高
- 描述：HDF5的`cashflow_cfo_to_net_profit_ratio`字段存储值0.680114，但反推发现其含义与列名不符：
  - HDF5净利润=4.71亿（非4.40亿），4.61/4.71=0.978（非0.68）
  - 用0.680114×4.71=3.21亿≠实际经营现金流4.61亿
  - 用4.61/0.680114=6.78亿≠任何合理净利润
- 根因：HDF5 cashflow表的匿名列f1-f8映射存在错误，`cfo_to_net_profit_ratio`实际含义未知（可能对应其他公司或旧年份数据）
- 影响：`_compute_metrics`直接使用`cashflow_cfo_to_net_profit_ratio`作为净现比，导致2024年净现比为0.68（错误），而akshare专家数据为0.98
- 建议方案：
  1. 当akshare可用时，优先使用akshare的`operating_cf / net_profit`计算净现比，完全忽略HDF5的`cfo_to_net_profit_ratio`
  2. 对HDF5降级场景，标记`confidence=low`并在字段名加后缀`hdf5_raw`以示区分
  3. 重新验证HDF5匿名列映射：用已知永新2015-2023年净现比（0.61-0.66）验证各f列真实含义

**2. [module2] `InvalidIndexError`导致`get_derived_metrics`在akshare+HDF5合并时崩溃**
- 严重程度：高
- 描述：`fetcher.py:_merge_one_row_per_year`中`pd.concat([df_ak, df_h5])`在akshare和HDF5均返回数据时触发pandas `InvalidIndexError`（非唯一索引冲突）。实测：永新002014 HDF5有9年数据，akshare超时30秒降级HDF5后正常；但若akshare成功返回数据则触发此bug
- 影响：`get_derived_metrics`完全不可用（见实测traceback）
- 建议方案：在concat前对两个DataFrame的索引去重/重置：
  ```python
  df_ak = df_ak.reset_index(drop=True) if not df_ak.empty else df_ak
  df_h5 = df_h5.reset_index(drop=True) if not df_h5.empty else df_h5
  ```

**3. [industry_thresholds] 阈值全部为占位符，三级降级从未真正触发**
- 严重程度：高
- 描述：
  - `confidence`返回`low`（正确诚实），但`source=fallback_market_wide`，意味着所有阈值均来自`FALLBACK_THRESHOLDS`
  - `_compute_industry_thresholds`虽然存在，但实际返回的是硬编码值`p10=0.50, p50=0.85`（注释说"已知合理值"）
  - 三级降级路径（SW3→SW2→SW1→全市场）从未真正执行：没有SW3/SW2的降级逻辑，无真实akshare数据计算
- 影响：医药生物行业P10=0.50/P50=0.85不是真实计算值，无法验证是否与行业实际相符
- 建议方案：
  1. 实现`_compute_industry_thresholds`：对申万行业成分股（限50只）批量拉取财务数据，真实计算分位数
  2. 在fetcher层实现三级降级：`try SW3 → except → try SW2 → except → try SW1 → except → fallback`
  3. 添加`akshare_computed`数据缓存（HDF5或pickle），避免每次重新拉取

### P2（建议修复）

**4. [module2] `calc_roic_simple`用净利润代替EBIT，忽略税收调整**
- 严重程度：中
- 描述：`calc_roic_simple`用`净利润/(总资产-流动负债)`代替ROIC，但标准ROIC=NOPAT/投入资本，NOPAT=EBIT×(1-tax_rate)。用净利润会高估ROIC（因为利息支出未加回）
- 另外：`calc_roic`（标准版）存在于calculator.py但从未在fetcher/api中被调用
- 建议方案：
  1. 在`api.py:get_derived_metrics`中优先调用`calc_roic`（标准版）
  2. `calc_roic_simple`作为无营业利润时的fallback，并添加注释说明误差方向

**5. [industry_thresholds] `get_red_flags`未处理`ar_growth`指标的阈值映射**
- 严重程度：中
- 描述：`INDICATOR_MAP`中没有`ar_growth`→`AR_GROWTH`的映射（但`FALLBACK_THRESHOLDS`中有`AR_GROWTH`），导致应收增速红旗检测缺失
- 另外`receivable_growth`列在`get_financial_history`中也未生成
- 建议方案：在`INDICATOR_MAP`中添加`'receivable_growth': 'AR_GROWTH'`，并在`calculator.py`中添加应收增速计算

**6. [module2] `get_industry_code`对永新以外股票完全依赖硬编码映射**
- 严重程度：中
- 描述：`_guess_industry_from_code`只有6个硬编码股票，其他股票均返回"未知"
- 建议方案：实现真实的akshare行业分类获取（`stock_board_industry_name_em`返回的是板块成分股，不是单只股票的行业映射）

### P3（低优先级/建议）

**7. [industry_thresholds] SW1行业列表有重复项**
- 严重程度：低
- 描述：`SW1_INDUSTRIES`列表中"汽车"出现了两次
- 建议：去重

**8. [industry_thresholds] `get_sw1_name`返回硬编码"医药生物"**
- 严重程度：低
- 描述：`get_sw1_name`方法忽略参数，返回固定值，完全未实现映射逻辑
- 建议：实现真实映射或删除此方法（当前未被调用）

---

## 验收标准达成情况复核

| 验收标准 | 达成情况 | 说明 |
|---------|---------|------|
| 永新近10年营收34.15亿(2024) | ✅ 确认HDF5返回34.15亿（2024） | HDF5数据对齐 |
| 永新ROE 18.54% | ✅ 确认HDF5 profit_roe=0.185367（18.54%） | 数据正确 |
| 永新净现比0.68 | ⚠️ **有异议**：HDF5确实返回0.68，但此值无法溯源，akshare专家说0.98 | 见问题#1 |
| 医药生物P10=0.50, P50=0.85 | ⚠️ **占位符**：非真实计算值 | 见问题#3 |
| 三大危险信号组合RED | ✅ 实测触发RED（red_count=2） | combos逻辑正确 |

---

## 总体评价

module2和industry_thresholds的基础架构合理（HDF5降级、akshare超时保护、三大危险信号组合逻辑均已实现），但核心数据质量问题（HDF5净现比溯源错误）、一处会导致崩溃的bug（concat索引冲突）以及行业阈值全为占位符（无真实计算）必须在G3之前修复。建议优先修复P1问题，数据质量确认后重新跑通验收测试。
