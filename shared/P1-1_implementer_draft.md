# P1-1 估值分析引擎 实施者方案初稿

**作者：** 实施者 subagent
**日期：** 2026-04-04
**状态：** 初稿，待评估者 review 并对齐

---

## 一、技术方案

### 1.1 架构风格

遵循 module5_red_flags 的 Block + Engine + Scorer + API 四件套模式：

```
module5_valuation/
├── api.py          # 对外入口：get_valuation(stock_code) → dict
├── engine.py       # 主编排逻辑：并行拉取各估值数据源
├── models.py       # Pydantic/dataclass 数据模型（ValuationBlock）
├── methods/
│   ├── pe_percentile.py   # PE/PB 历史分位
│   ├── dcf.py             # DCF 自由现金流折现
│   ├── graham.py          # 格雷厄姆公式
│   └── dividend_discount.py  # 股息折现（适合高股息股）
├── reports/        # JSON 报告输出目录
└── __init__.py
```

### 1.2 估值方法选型

| 方法 | 适用场景 | 技术说明 |
|------|---------|---------|
| **PE 历史分位** | 通用，盈利稳定公司 | 以申万三级行业为基准，计算当前 PE 在历史分位数（P10/P30/P50/P70/P90）；依赖行业阈值库已有分位数基础设施 |
| **PB 历史分位** | 金融、周期、重资产 | 同上，区别在于用 PB 而非 PE |
| **DCF（两阶段）** | 成长型公司 | 详细见下方「DCF 分阶段说明」 |
| **格雷厄姆数** | 保守型价值投资 | 公式：`sqrt(22.5 × EPS × BVPS)`，适合消费、医药等稳定盈利公司 |
| **股息折现（DDM）** | 高股息、成熟行业 | `PV = D1 / (r - g)`，适用于公用事业、金融 |

**DCF 两阶段说明：**

```
阶段1（显式期）：5年 explicit forecast
  - 手动设定 5 年 FCF 增长率（默认 10%/年，可调整）
  - 折现率 = 无风险利率（10年国债）+ Beta × ERP + 特定风险溢价
  - Beta 来源：akshare 或 HISTOCK

阶段2（终值）：
  - Gordon 永续增长模型：TV = FCF_n × (1+g) / (WACC - g)
  - 永续增速 g 默认 3%（名义 GDP 增速）

WACC 构成：
  - r_e = Rf + Beta × ERP  （ERP = 5.5%，Rf = 当前 10年国债）
  - r_d = 贷款基准利率 × (1 - 税率)
  - WACC = E/(D+E) × r_e + D/(D+E) × r_d × (1-T)
```

**各方法的优先级规则（内部评分权重）：**

```
1. PE/PB 分位：基础权重 40%（龙头/价值股更高）
2. DCF：权重 30%（成长股权重提升至 50%）
3. 格雷厄姆数：权重 20%（适合低 PE/BV 的稳健公司）
4. DDM：权重 10%（高股息股反之提升）
```

### 1.3 置信度机制

每个方法输出 `confidence: high/medium/low`，由数据完整度决定：

- `high`：所有必需字段齐全，历史数据 ≥ 5 年
- `medium`：必需字段 80% 齐全，历史数据 2-4 年
- `low`：数据缺失较多或不足 2 年

---

## 二、数据需求

### 2.1 来自现有模块的数据

| 数据源 | 模块 | 字段 | 用途 |
|--------|------|------|------|
| 历史财务数据 | module2_financial | 净利润、EPS、总股本、每股净资产（BVPS）、营业收入、经营现金流（OCF）、自由现金流（FCF）、总股本 | PE、PB、DCF、格雷厄姆数 |
| 历史价格 | akshare 直接获取 | 月度/日度收盘价序列 | PE/PB 历史分位计算 |
| 行业分类 | industry_thresholds | 申万三级行业代码 | PE/PB 分位基准 |
| Beta 值 | akshare | 个股 Beta（可选，降级用市场 Beta=1.0） | DCF WACC |
| 无风险利率 | 手动更新/定时爬取 | 10 年期国债收益率 | DCF 折现率 |
| 分红数据 | module2_financial 或 akshare | 近 5 年股息率、DPS | DDM |

### 2.2 来自行业阈值库的能力

调用 `industry_thresholds/api.py` 已有接口：

```python
# 用行业分位数判断当前 PE/PB 的相对高低
from industry_thresholds.api import get_threshold, get_industry_class

industry = get_industry_class(stock_code)  # "医药生物"
pe_p50 = get_threshold(industry, "PE", percentile=50)
pe_p70 = get_threshold(industry, "PE", percentile=70)
# 当前 PE < pe_p50 → 低估；当前 PE > pe_p70 → 高估
```

行业阈值库目前支持指标：`CFO_TO_REVENUE`, `ROE`, `REVENUE_GROWTH`, `GROSS_MARGIN`, `DEBT_RATIO`, `NET_MARGIN`。

**需要扩展：** 新增 `PE` 和 `PB` 两个指标的分位数存储和查询接口，使估值引擎可以直接复用。

### 2.3 新增数据获取

| 数据 | 来源 | 备注 |
|------|------|------|
| 10 年国债收益率 | 手动配置或爬取（稳定值，不需要实时） | 当前约 1.8%，每季度更新 |
| 市场 ERP | 需配置（建议默认 5.5%） | 学术/业界通用值 |
| Beta | akshare 或降级市场 Beta=1.0 | 如获取失败，记录 warning |

---

## 三、与现有模块集成

### 3.1 集成模式

完全遵循 module5_red_flags 的延迟导入 + 信号量超时模式：

```python
# engine.py 中的数据获取函数签名
def _fetch_financial(stock_code: str, years: int = 10) -> pd.DataFrame:
    """调用 module2_financial 返回历史财务 DataFrame"""

def _fetch_industry_thresholds(stock_code: str) -> Dict:
    """调用 industry_thresholds，返回 PE/PB 分位数阈值"""

def _fetch_price_history(stock_code: str, years: int = 10) -> pd.DataFrame:
    """akshare 拉取历史价格，计算 PE/PB 序列"""
```

### 3.2 与 module5_red_flags 的关系

**并行关系，非依赖：**

- module5_red_flags（红旗引擎）→ 评估财务质量和治理风险
- module5_valuation（估值引擎）→ 评估股价高低

两者在**模块8（投资结论引擎）**中汇合，由模块8做综合判断。

**共享基础设施：**

- 均使用 `industry_thresholds` 获取行业上下文
- 均使用 `module2_financial` 获取财务数据
- 均使用同一套 `reports/` 目录保存 JSON

### 3.3 与 chart_14（PE/PB 分位图）的接口

估值引擎输出结构化数据，图表模块直接消费：

```python
# 输出字段（供图表使用）
{
  "pe_percentile": 0.35,        # 当前 PE 历史分位（0-1）
  "pb_percentile": 0.42,
  "pe_history": [...],           # 年度 PE 序列 [{year, pe, pb}, ...]
  "industry_pe_p50": 28.5,      # 行业中位数 PE
  "industry_pe_p70": 35.2,      # 行业中位数 PE P70
}
```

---

## 四、输出格式

### 4.1 主报告结构

```json
{
  "stock_code": "002014",
  "stock_name": "永新股份",
  "report_date": "2026-04-04",
  "verdict": "低估",
  "overall_score": 72,

  "current_price": 12.50,
  "market_cap": 6200000000,

  "methods": {
    "pe_percentile": {
      "confidence": "high",
      "current_pe": 18.5,
      "pe_percentile": 0.28,
      "industry_pe_p50": 22.1,
      "industry_pe_p70": 28.0,
      "signal": "低估",
      "reason": "PE 18.5处于历史分位28%，低于行业中位数22.1"
    },
    "pb_percentile": {
      "confidence": "medium",
      "current_pb": 2.1,
      "pb_percentile": 0.55,
      "industry_pb_p50": 2.5,
      "signal": "合理"
    },
    "dcf": {
      "confidence": "medium",
      "intrinsic_value": 15.80,
      "upside_pct": 26.4,
      "wacc": 0.092,
      "stage1_growth_rate": 0.10,
      "terminal_growth_rate": 0.03,
      "signal": "低估"
    },
    "graham": {
      "confidence": "high",
      "graham_number": 14.20,
      "upside_pct": 13.6,
      "current_price_vs_graham": "高于格雷厄姆数，当前价格已偏高"
    },
    "ddm": {
      "confidence": "low",
      "intrinsic_value": null,
      "reason": "股息率数据不足"
    }
  },

  "consensus": {
    "signal": "低估",
    "primary_method": "pe_percentile",
    "upside_pct": 18.5,
    "downside_risk_pct": -12.0,
    "summary": "PE分位28%处于历史低位，DCF显示内在价值15.8元，较当前价有26%上涨空间"
  },

  "risk_factors": [
    {
      "factor": "PE分位较低可能反映市场对该行业的系统性折价",
      "severity": "medium"
    }
  ],

  "data_quality": {
    "pe_history_years": 8,
    "financial_data_years": 8,
    "industry_threshold_confidence": "high"
  }
}
```

### 4.2 估值结论判定规则

```
verdict = "显著低估"  当 至少2个方法显示低估 且 平均上行空间 > 30%
verdict = "低估"      当 至少2个方法显示低估 且 平均上行空间 10-30%
verdict = "合理"      当 无明显偏差
verdict = "高估"      当 至少2个方法显示高估 且 平均下行空间 > 10%
verdict = "数据不足"  当 有效方法 < 2 个
```

---

## 五、开放问题（需要评估者确认）

### Q1：DCF 参数谁来设定？

当前方案采用「合理默认参数 + 可覆盖」策略：

- WACC 通过公式自动计算（国债 + Beta × ERP）
- 阶段1增长率默认 10%/年，用户可传参覆盖

**问题：是否需要支持用户主动输入 WACC 和增长率（敏感参数）？**
还是说系统只输出「标准参数下的 DCF 结果」而不暴露参数调节能力？

---

### Q2：PE/PB 历史分位的基准池是什么？

当前方案：以**申万三级行业平均 PE/PB 分位数**作为基准。

**问题：基准池是否需要支持切换？**（例如：可以选「全市场平均」vs「行业平均」vs「可比公司平均」）

---

### Q3：PE 为负（亏损公司）如何处理？

亏损公司 PE 为负，PE 分位方法失效。当前方案：PE 负值时自动跳过 PE 分位方法，降权到 DCF（需正现金流）或格雷厄姆数。

**问题：是否需要增加「困境反转」特殊模式，对亏损公司使用 PB + 清算价值下限作为估值？**

---

### Q4：格雷厄姆数公式选择哪个版本？

格雷厄姆在《聪明的投资者》中给出两个版本：

- 原版：`sqrt(22.5 × EPS × BVPS)` — 保守，适合成熟公司
- 修正版：`sqrt(15 × EPS × (8.5 + 2g))` — 考虑成长率 g

**问题：默认使用原版还是修正版？是否需要参数化？**

---

### Q5：行业阈值库需要扩展 PE/PB 分位数

当前 `industry_thresholds` 表没有 PE 和 PB 的历史分位数存储。

**问题：**

1. 是扩展现有 `indicator_thresholds` 表（新增 PE/PB 指标），还是新建专用表 `valuation_thresholds`？
2. PE/PB 的 red_flag 阈值怎么定？（比如 PE < P20 算低估，P80 算高估 — 这与财务质量红旗逻辑不同）

---

## 六、初步工作量估算

| 任务 | 估算 | 依赖 |
|------|------|------|
| 扩展 industry_thresholds 支持 PE/PB | 1 天 | 无 |
| models.py（数据模型） | 0.5 天 | 无 |
| pe_percentile.py | 1 天 | industry_thresholds 扩展 |
| pb_percentile.py | 0.5 天 | 同上 |
| dcf.py | 1.5 天 | 无 |
| graham.py | 0.5 天 | 无 |
| ddm.py | 0.5 天 | 无 |
| engine.py（主编排） | 1 天 | 上述所有 |
| api.py | 0.5 天 | engine.py |
| 测试（3-5 只股票） | 1 天 | 全部 |
| **合计** | **~8 天** | |
