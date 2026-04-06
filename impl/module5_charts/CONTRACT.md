# 模块5图表自动化模块实施合同

**文档编号**: P1-M5-CONTRACT  
**版本**: v2.0（评审裁定版）  
**创建日期**: 2026-04-06  
**修订日期**: 2026-04-06  
**角色**: 执行者=Architect，评估者=Tester，裁定=Main  
**状态**: ✅ 合同已裁定，签署后生效

---

## 一、任务范围

### 1.1 项目背景

图表自动化模块是A股深度分析系统的可视化输出层，基于模块2（财务数据模块）的结构化数据和模块6（MD&A分析模块）的文本分析结果，批量生成15张高质量静态图表。

### 1.2 交付物清单

| 序号 | 交付物 | 说明 |
|------|--------|------|
| M5-D1 | 图表生成器核心模块 | `chart_generator.py` |
| M5-D2 | 图表配置文件 | `chart_config.yaml` — 15张图表完整规格定义 |
| M5-D3 | 财务分析图表集 | 10张财务分析图表 |
| M5-D4 | MD&A可视化图表集 | 5张MD&A可视化图表 |
| M5-D5 | 测试用例 | 单元测试 + 集成测试 |
| M5-D6 | 使用文档 | `README.md` |

### 1.3 图表清单（15张）— 最终裁定版

**财务模块（6张）**

| 序号 | 图表名称 | 类型 | 数据来源 | 优先级 |
|------|----------|------|----------|--------|
| 1 | 营收/净利润趋势 | 双轴折线图 | 模块2 | P0 |
| 2 | ROIC vs WACC趋势 | 折线图 | 模块2 | P0 |
| 3 | 杜邦三因子贡献堆叠 | 堆叠面积图 | 模块2 | P0 |
| 4 | EPS + DPS + 累计分红 | 柱+线组合图 | 模块2 | P0 |
| 5 | 现金流去向堆叠 | 堆叠柱状图 | 模块2 | P1 |
| 6 | 资产负债率+有息负债率 | 双轴折线图 | 模块2 | P0 |

**估值模块（3张）**

| 序号 | 图表名称 | 类型 | 数据来源 | 优先级 |
|------|----------|------|----------|--------|
| 7 | PE/PB/PS历史分位 | 箱线图 | 模块2 | P1 |
| 8 | DCF敏感性热力图 | 热力图 | 模块2 | P1 |
| 9 | 相对估值横向比较 | 柱状图 | 模块2 | P2 |

**季节性模块（2张）**

| 序号 | 图表名称 | 类型 | 数据来源 | 优先级 |
|------|----------|------|----------|--------|
| 10 | 季度营收/利润波动柱状图 | 柱状图 | 模块2 | P1 |
| 11 | 季节性热力图（环比+同比） | 热力图 | 模块2 | P1 |

**MD&A模块（3张）**

| 序号 | 图表名称 | 类型 | 数据来源 | 优先级 |
|------|----------|------|----------|--------|
| 12 | 管理层讨论要点词云 | 词云 | 模块6 | P2 |
| 13 | 经营风险趋势 | 时间线 | 模块6 | P1 |
| 14 | 行业环境评估雷达 | 雷达图 | 模块6 | P1 |

**综合模块（1张）**

| 序号 | 图表名称 | 类型 | 数据来源 | 优先级 |
|------|----------|------|----------|--------|
| 15 | 核心指标仪表盘 | 组合仪表盘 | 模块2+6 | P0 |

---

## 二、验收标准

### 2.1 功能验收

| 验收项 | 验收条件 | 测试方法 |
|--------|----------|----------|
| 图表生成成功 | 15张图表全部成功生成，无异常 | 运行生成器，检查输出文件 |
| 数据完整性 | 每张图表正确读取对应数据字段 | 数据追踪 + 断点检查 |
| 中文显示 | 中文标签正确显示，无乱码 | 字体配置验证 |
| 文件输出 | PNG格式，分辨率≥150dpi | 文件属性检查 |
| 批量生成 | 单股票15张图表生成时间≤30秒 | 性能测试 |

### 2.2 质量验收

| 验收项 | 验收条件 | 标准 |
|--------|----------|------|
| 图表配色 | 符合A股惯例（红涨绿跌） | 配色方案审查 |
| 布局合理性 | 图表元素不重叠，比例协调 | 目视检查 |
| 异常处理 | 数据缺失时图表降级显示"数据不可用" | 异常注入测试 |
| 中文乱码 | 字体fallback链验证 | 多字体环境测试 |

### 2.3 交付验收checklist

- [ ] `chart_generator.py` 可独立运行
- [ ] `chart_config.yaml` 包含15张图表完整配置
- [ ] 输出目录含15张PNG图表
- [ ] 中文字体fallback链测试通过
- [ ] 单元测试覆盖率≥60%
- [ ] README.md 包含使用说明

---

## 三、数据接口Schema（附录A）

> **⚠️ 数据接口是合同必须部分，实施前必须完成Schema定义。**

### 模块2 → 模块5 数据Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["stock_code", "years", "financial_metrics"],
  "properties": {
    "stock_code": {"type": "string", "description": "股票代码"},
    "years": {"type": "array", "items": {"type": "integer"}, "description": "数据年份列表"},
    "financial_metrics": {
      "type": "object",
      "required": ["revenue", "net_profit", "roe", "roic", "eps", "dps", "cfo", "total_assets", "net_assets", "gross_margin", "debt_ratio"],
      "properties": {
        "revenue": {"type": "array", "items": {"type": "number"}, "description": "营业收入序列"},
        "net_profit": {"type": "array", "items": {"type": "number"}, "description": "净利润序列"},
        "roe": {"type": "array", "items": {"type": "number"}, "description": "ROE序列"},
        "roic": {"type": "array", "items": {"type": "number"}, "description": "ROIC序列"},
        "wacc": {"type": "array", "items": {"type": "number"}, "description": "WACC序列"},
        "eps": {"type": "array", "items": {"type": "number"}, "description": "EPS序列"},
        "dps": {"type": "array", "items": {"type": "number"}, "description": "DPS序列"},
        "cfo": {"type": "array", "items": {"type": "number"}, "description": "经营现金流序列"},
        "total_assets": {"type": "array", "items": {"type": "number"}, "description": "总资产序列"},
        "net_assets": {"type": "array", "items": {"type": "number"}, "description": "净资产序列"},
        "gross_margin": {"type": "array", "items": {"type": "number"}, "description": "毛利率序列"},
        "debt_ratio": {"type": "array", "items": {"type": "number"}, "description": "资产负债率序列"},
        "interest_bearing_debt_ratio": {"type": "array", "items": {"type": "number"}, "description": "有息负债率序列"},
        "pe": {"type": "array", "items": {"type": "number"}, "description": "PE序列"},
        "pb": {"type": "array", "items": {"type": "number"}, "description": "PB序列"},
        "ps": {"type": "array", "items": {"type": "number"}, "description": "PS序列"},
        "dupont_net_margin": {"type": "array", "items": {"type": "number"}, "description": "杜邦-净利率序列"},
        "dupont_asset_turnover": {"type": "array", "items": {"type": "number"}, "description": "杜邦-资产周转率序列"},
        "dupont_equity_multiplier": {"type": "array", "items": {"type": "number"}, "description": "杜邦-权益乘数序列"},
        "cumulative_dps": {"type": "array", "items": {"type": "number"}, "description": "累计分红序列"},
        "quarterly_revenue": {"type": "array", "items": {"type": "number"}, "description": "季度营收（4*N）"},
        "quarterly_profit": {"type": "array", "items": {"type": "number"}, "description": "季度净利润（4*N）"}
      }
    }
  }
}
```

### 模块6 → 模块5 数据Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["stock_code", "strategic_commitments", "key_strategic_themes", "risk_factors"],
  "properties": {
    "stock_code": {"type": "string"},
    "strategic_commitments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "commitment": {"type": "string"},
          "time_horizon": {"type": "string"},
          "quantitative_target": {"type": "string"}
        }
      }
    },
    "key_strategic_themes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "theme": {"type": "string"},
          "description": {"type": "string"}
        }
      }
    },
    "risk_factors": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "risk": {"type": "string"},
          "mitigation": {"type": "string"}
        }
      }
    }
  }
}
```

---

## 四、技术方案

### 4.1 技术选型

| 组件 | 选择 | 说明 |
|------|------|------|
| 绘图框架 | matplotlib 3.8+ | 成熟稳定 |
| 样式增强 | seaborn 0.12+ | 快速美化 |
| 配置管理 | PyYAML | 声明式图表配置 |
| 中文字体 | **4级fallback链** | 裁定通过 |
| 词云生成 | wordcloud | MD&A词云专用 |

### 4.2 中文字体fallback链（裁定版）

```python
import matplotlib.pyplot as plt

FONT_FALLBACK_CHAIN = [
    'SimHei',
    'Microsoft YaHei',
    'PingFang SC',
    'Arial'
]

for font in FONT_FALLBACK_CHAIN:
    try:
        plt.rcParams['font.sans-serif'] = [font]
        plt.rcParams['axes.unicode_minus'] = False
        break
    except Exception:
        continue
```

### 4.3 架构设计

```
chart_generator.py
├── ChartConfig (chart_config.yaml)
│   ├── 15张图表配置（含chart spec）
│   ├── 配色方案
│   └── 输出格式
├── DataLoader
│   ├── FinancialDataLoader → 模块2 JSON
│   └── MD&ADataLoader → 模块6 JSON
├── ChartFactory
│   ├── LineChart / BarChart / RadarChart
│   ├── Heatmap / WordCloud / Dashboard
└── OutputManager
    ├── PNGExporter (≥150dpi)
    └── BatchGenerator
```

---

## 五、时间估算

| 阶段 | 任务 | 工时 |
|------|------|------|
| 1 | Schema确认 + ChartConfig设计 | 2h |
| 2 | DataLoader实现（模块2+6） | 4h |
| 3 | ChartFactory基础框架 | 6h |
| 4 | 财务图表6张（P0）实现 | 8h |
| 5 | 估值+季节性图表5张（P1）实现 | 6h |
| 6 | MD&A图表3张实现 | 5h |
| 7 | 综合仪表盘1张（P0）实现 | 2h |
| 8 | 中文字体调试 + 异常处理 | 4h |
| 9 | 单元测试 + 集成测试 | 6h |
| 10 | 文档 + 交付 | 2h |
| **合计** | | **45h** |

### 里程碑

| 里程碑 | 交付物 | 预计 |
|--------|--------|------|
| M1 | Schema + ChartConfig + DataLoader | D+1 |
| M2 | 财务图表6张 + 仪表盘1张 | D+3 |
| M3 | 估值+季节性图表5张 | D+4 |
| M4 | MD&A图表3张 + 测试通过 | D+5 |

---

## 六、风险清单

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 模块2数据格式变化 | 图表生成失败 | Schema校验 + 降级策略 |
| 模块6输出不稳定 | MD&A图表异常 | 空值处理fallback |
| 中文字体缺失 | 图表乱码 | 4级fallback链 |
| 性能瓶颈 | 生成>30秒 | 异步渲染 + 缓存 |

---

## 七、合同签署

| 角色 | 签署 | 日期 |
|------|------|------|
| 评估者（Tester） | 待签 | |
| 执行者（Architect） | 待签 | |
| 审批人（Main） | 2026-04-06 | ✅ 已裁定 |

---

*附录A：数据接口Schema（必须实施前完成）*  
*附录B：图表规格定义（见 chart_config.yaml）*
