# -*- coding: utf-8 -*-
"""
模块8：投资结论引擎

A股深度分析系统的最终输出层

主要组件：
- ScoringModel: 多因子评分模型
- ResultAggregator: 结果聚合器
- InvestmentEngine: 投资结论引擎
- ReportGenerator: 报告生成器
- InvestmentConclusion: 投资结论数据类

使用示例：
```python
from module8_investment_conclusion import InvestmentEngine

engine = InvestmentEngine()
result = engine.analyze(
    stock_code='000858',
    stock_name='五粮液',
    financial_data={...},
    red_flag_data={...},
    mda_data={...},
    announcement_data={...},
    governance_data={...},
)
print(result.recommendation)  # 强烈买入/买入/持有/卖出/强烈卖出
```
"""

from .scoring_model import (
    ScoringModel,
    ScoreDetails,
    InvestmentConclusion,
)
from .aggregator import (
    ResultAggregator,
    AggregatedData,
)
from .investment_engine import (
    InvestmentEngine,
)
from .report_generator import (
    ReportGenerator,
)

__all__ = [
    # 评分模型
    'ScoringModel',
    'ScoreDetails',
    'InvestmentConclusion',
    # 聚合器
    'ResultAggregator',
    'AggregatedData',
    # 引擎
    'InvestmentEngine',
    # 报告生成
    'ReportGenerator',
]

# 版本信息
__version__ = '1.0.0'
