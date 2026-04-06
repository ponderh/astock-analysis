# industry_thresholds: 行业阈值数据库

## 概述

计算申万一级行业（28个）的各指标分位数阈值，实现`get_threshold`和`get_red_flags` API，包含三大危险信号组合逻辑。

## 目录结构

```
industry_thresholds/
├── __init__.py       # 导出主要API
├── fetcher.py         # IndustryThresholdFetcher: 数据获取+阈值计算
├── combos.py          # 三大危险信号组合逻辑
├── api.py            # get_threshold(), get_red_flags() 等对外接口
└── README.md
```

## 快速使用

```python
from industry_thresholds import get_threshold, get_red_flags, check_combo_flags

# 获取医药生物行业净现比P10/P50
th = get_threshold("医药生物", "CFO_TO_REVENUE", percentile=10)
print(th)  # {'value': 0.5, 'red_flag': 0.3, ...}

# 获取某只股票的红旗信号
from module2_financial.api import get_financial_history
df = get_financial_history("002014")
flags = get_red_flags("002014", df)
print(flags)

# 检查三大危险信号组合
combo = check_combo_flags(df)
print(combo['overall_severity'])
```

## 核心API

### `get_threshold(industry, indicator, percentile=None)`
获取某行业的指标分位数阈值。

| 参数 | 说明 |
|------|------|
| industry | 行业名称，如"医药生物" |
| indicator | 指标代码，见下表 |
| percentile | 分位数 5/10/25/50/75/90/95，若为None返回完整表 |

**支持指标：**

| 指标代码 | 说明 | P10(红旗) | P50(中位) |
|---------|------|---------|---------|
| CFO_TO_REVENUE | 净现比 | 0.50 | 0.85 |
| ROE | 净资产收益率 | 5% | 10% |
| REVENUE_GROWTH | 营收增速 | -5% | 12% |
| GROSS_MARGIN | 毛利率 | 15% | 30% |
| DEBT_RATIO | 资产负债率 | 20% | 45% |
| NET_MARGIN | 净利率 | 3% | 8% |
| AR_GROWTH | 应收增速 | -10% | 10% |

### `get_red_flags(stock_code, financial_data, report_date=None)`
返回某只股票的红旗信号列表，每个信号包含：
- `indicator`: 指标代码
- `actual`: 实际值
- `threshold`: 红旗阈值
- `severity`: RED / GREEN

### `check_combo_flags(financial_data)`
检查三大危险信号组合，返回汇总结果。

## 三大危险信号组合

### 1. cfo_ar_combo: 现金流恶化+应收异常
**触发条件**: 净现比<0.8（连续2年）**且**应收增速>营收增速×1.3（连续2年）
**严重程度**: 🔴 RED，权重4

### 2. double_surge: 存货+应收账款双激增
**触发条件**: 存货增速>营收增速+15% **且**应收增速>营收增速+20%
**严重程度**: 🔴 RED，权重3

### 3. margin_up_inventory_down: 毛利率升+周转降
**触发条件**: 毛利率提升>3pct **但**周转天数下降>15%
**严重程度**: 🔴 RED，权重4（需人工核查）

## 三级降级机制

当某行业数据不足时，自动降级：
1. **精确**: 申万三级行业（SW3）
2. **Fallback 1**: 申万二级行业（SW2）
3. **Fallback 2**: 申万一级行业（SW1）
4. **Fallback 3**: 全市场占位符（已知合理值）

## 已知限制

- 当前使用全市场占位符作为阈值（akshare全量数据拉取较慢）
- `confidence`字段标注数据质量（high/medium/low）
- 申万行业映射使用已知占位符，未接入真实行业分类API
