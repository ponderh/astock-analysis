# module2_financial: 历史财务数据管道

## 概述

从akshare拉取A股财务数据，计算ROIC/杜邦分解/现金流分析，提供标准化API供下游模块调用。

## 数据源

- **主数据源**: akshare `stock_financial_analysis_indicator`（东方财富财务指标）
- **辅助数据源**: HDF5历史数据库（`astock-strategy-v3/data/a_stock_financial.h5`）
- **超时保护**: akshare获取设置30秒超时，超时自动降级到HDF5

## 目录结构

```
module2_financial/
├── __init__.py       # 导出主要API
├── fetcher.py         # FinancialFetcher: 数据获取（akshare+HDF5）
├── calculator.py      # calc_roic, dupont_decompose, cashflow_analysis
├── api.py            # get_financial_history() 等对外接口
└── README.md
```

## 快速使用

```python
from module2_financial.api import get_financial_history

# 获取永新股份近10年财务数据
df = get_financial_history("002014", years=10)
print(df[['statDate','revenue','roe','cfo_to_net_profit']])
```

## 核心函数

### `get_financial_history(stock_code, years=10)`
返回包含以下列的DataFrame（1行/年）：

| 列名 | 说明 |
|------|------|
| statDate | 财报期末 |
| pubDate | 公告日期 |
| revenue | 营业收入（元） |
| net_profit | 净利润（元） |
| roe | 净资产收益率 |
| roic | 投资资本回报率（计算） |
| cfo_to_net_profit | 净现比 |
| revenue_growth | 营收增速 |
| profit_growth | 净利润增速 |
| data_source | akshare / hdf5 |
| gaap_breakpoint | PRE_2007 / POST_2007 |

### `calc_roic(operating_income, tax_rate, total_assets, current_liabilities, equity)`
ROIC = NOPAT / Invested Capital

### `dupont_decompose(roe)` / `dupont_from_components(...)`
ROE三因子分解：净利率 × 资产周转率 × 权益乘数

### `cashflow_analysis(operating_cf, net_profit, investing_cf, financing_cf)`
现金流质量分析：净现比、现金流质量评级

## 无前视偏差设计

- 所有指标使用当期财报数据计算
- `pubDate` 字段标注数据公告时间（财报期末+约60天）
- `gaap_breakpoint` 标注2007新会计准则断点

## HDF5列名映射（逆向推导）

| HDF5表 | 匿名列 | 标准列名 |
|--------|--------|---------|
| profit | f1 | roe |
| profit | f4 | net_profit（元） |
| profit | f6 | revenue（元） |
| cashflow | f1 | cfo_to_net_profit_ratio（净现比） |
| dupont | f1 | roe |
| balance | f3 | equity |

## 已知限制

- akshare在部分网络环境下拉取较慢（>30秒），已实现超时保护
- HDF5数据覆盖2015-2024年，2019年数据缺失（无法拉取）
- akshare拉取成功时会替代HDF5数据
