"""
module2_financial: 历史财务数据管道
====================================
目标：拉取近10年财务数据，计算ROIC/杜邦分解/现金流分析
数据源：akshare为主，HDF5历史数据为辅
输出：标准化API供下游模块调用
"""

from .fetcher import FinancialFetcher
from .calculator import (
    calc_roic,
    dupont_decompose,
    cashflow_analysis,
    calc_net_cash_ratio,
)
from .api import get_financial_history, get_derived_metrics

__all__ = [
    "FinancialFetcher",
    "calc_roic",
    "dupont_decompose", 
    "cashflow_analysis",
    "calc_net_cash_ratio",
    "get_financial_history",
    "get_derived_metrics",
]
