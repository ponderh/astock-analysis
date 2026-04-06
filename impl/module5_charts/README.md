# 模块5：图表自动化模块

**状态**: Phase 1 完成 ✅  
**版本**: v2.0（评审裁定版）

---

## 概述

图表自动化模块是A股深度分析系统的可视化输出层，基于模块2（财务数据模块）的结构化数据和模块6（MD&A分析模块）的文本分析结果，批量生成15张高质量静态图表。

---

## Phase 1 交付物

| 文件 | 说明 |
|------|------|
| `financial_loader.py` | 财务数据加载器，对接模块2 |
| `mda_loader.py` | MD&A数据加载器，对接模块6 |
| `chart_config.yaml` | 15张图表完整配置定义 |
| `README.md` | 本文档 |

### 目录结构

```
module5_charts/
├── financial_loader.py    # 财务数据加载器
├── mda_loader.py          # MD&A数据加载器
├── chart_config.yaml      # 图表配置
├── README.md              # 本文档
├── output/                # 图表输出目录
└── CONTRACT.md            # 合同文档
```

---

## 数据加载器

### FinancialDataLoader

负责加载和验证模块2输出的财务数据。

**功能特性：**
- JSON文件加载
- 严格Schema校验（按CONTRACT.md附录A）
- 数据字段访问接口
- 便捷函数支持

**使用示例：**

```python
from financial_loader import FinancialDataLoader

# 方式1: 指定文件路径
loader = FinancialDataLoader()
data = loader.load('/path/to/000001_financial.json')

# 方式2: 从数据目录加载
loader = FinancialDataLoader(data_dir='./data')
data = loader.load_from_dir('000001')

# 访问数据
revenue = loader.get_revenue()
years = loader.get_years()
metrics = loader.get_financial_metrics()
```

**Schema校验：**
- 必需字段：`stock_code`, `years`, `financial_metrics`
- 必需财务指标：revenue, net_profit, roe, roic, eps, dps, cfo, total_assets, net_assets, gross_margin, debt_ratio
- 可选字段：wacc, pe, pb, ps, 杜邦因子等

---

### MD&ADataLoader

负责加载和验证模块6输出的MD&A分析数据。

**功能特性：**
- JSON文件加载
- 严格Schema校验（按CONTRACT.md附录A）
- 文本提取（用于词云）
- 战略承诺/风险因素访问

**使用示例：**

```python
from mda_loader import MD&ADataLoader

# 方式1: 指定文件路径
loader = MD&ADataLoader()
data = loader.load('/path/to/000001_mda.json')

# 方式2: 从数据目录加载
loader = MD&ADataLoader(data_dir='./data')
data = loader.load_from_dir('000001')

# 访问数据
commitments = loader.get_strategic_themes()
risks = loader.get_risk_factors()

# 获取所有文本（用于词云）
all_texts = loader.get_all_texts()
```

**Schema校验：**
- 必需字段：`stock_code`, `strategic_commitments`, `key_strategic_themes`, `risk_factors`
- 每个数组项包含：commitment, time_horizon, quantitative_target 等

---

## ChartConfig.yaml 说明

### 全局配置

```yaml
global:
  font_fallback:           # 中文字体fallback链（4级）
    - SimHei
    - Microsoft YaHei
    - PingFang SC
    - Arial
  figure_size:             # 图表尺寸
    width: 12
    height: 8
  dpi: 150                # 分辨率
```

### 配色方案

```yaml
colors:
  bullish: "#E74C3C"     # 红色 - 上涨
  bearish: "#27AE60"     # 绿色 - 下跌
  primary: "#2C3E50"     # 主色调
  series:                # 图表系列配色
    - "#3498DB"
    - "#E74C3C"
    ...
```

### 图表配置结构

每个图表包含：
- `name`: 图表名称
- `type`: 图表类型（line, bar, heatmap, radar等）
- `priority`: P0/P1/P2
- `data_source`: module2 或 module6
- `metrics`: 数据字段映射
- `axis_labels`: 坐标轴标签
- `colors`: 配色

---

## 15张图表清单

| # | 图表名称 | 类型 | 数据源 | 优先级 |
|---|----------|------|--------|--------|
| 1 | 营收/净利润趋势 | 双轴折线图 | 模块2 | P0 |
| 2 | ROIC vs WACC趋势 | 折线图 | 模块2 | P0 |
| 3 | 杜邦三因子贡献堆叠 | 堆叠面积图 | 模块2 | P0 |
| 4 | EPS + DPS + 累计分红 | 柱+线组合图 | 模块2 | P0 |
| 5 | 现金流去向堆叠 | 堆叠柱状图 | 模块2 | P1 |
| 6 | 资产负债率+有息负债率 | 双轴折线图 | 模块2 | P0 |
| 7 | PE/PB/PS历史分位 | 箱线图 | 模块2 | P1 |
| 8 | DCF敏感性热力图 | 热力图 | 模块2 | P1 |
| 9 | 相对估值横向比较 | 柱状图 | 模块2 | P2 |
| 10 | 季度营收/利润波动 | 柱状图 | 模块2 | P1 |
| 11 | 季节性热力图 | 热力图 | 模块2 | P1 |
| 12 | 管理层讨论要点词云 | 词云 | 模块6 | P2 |
| 13 | 经营风险趋势 | 时间线 | 模块6 | P1 |
| 14 | 行业环境评估雷达 | 雷达图 | 模块6 | P1 |
| 15 | 核心指标仪表盘 | 组合仪表盘 | 模块2+6 | P0 |

---

## 技术要求

### 中文字体fallback链

```python
FONT_FALLBACK_CHAIN = [
    'SimHei',
    'Microsoft YaHei',
    'PingFang SC',
    'Arial'
]
```

### Schema校验

所有数据加载必须通过Schema校验：
- 不符合Schema的数据抛出 `SchemaValidationError`
- 错误信息包含具体的字段缺失或类型错误

### 异常处理

| 场景 | 处理策略 |
|------|----------|
| 数据缺失 | 显示"数据不可用"占位符 |
| Schema验证失败 | 抛出异常，明确错误原因 |
| 字体缺失 | 尝试fallback链，记录日志 |

---

## 下一步（Phase 2+）

- [ ] ChartFactory 工厂模式实现
- [ ] chart_generator.py 核心生成器
- [ ] 15张图表逐一实现
- [ ] 单元测试 + 集成测试
- [ ] 批量生成优化

---

## 参考

- CONTRACT.md - 完整合同定义
- 模块2数据输出规格
- 模块6数据输出规格