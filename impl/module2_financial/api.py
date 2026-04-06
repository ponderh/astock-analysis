"""
api.py: 对外API接口
===================
供下游模块调用的标准化接口
"""

from typing import Optional, Dict, List
import numpy as np
import pandas as pd

from .fetcher import FinancialFetcher
from .calculator import (
    compute_all_metrics,
    calc_roic_simple,
    dupont_from_components,
    cashflow_analysis,
    calc_net_cash_ratio,
    roe_vs_wacc,
)

# 全局单例fetcher（避免重复初始化）
_global_fetcher: Optional[FinancialFetcher] = None


def get_fetcher(hdf5_only: bool = False) -> FinancialFetcher:
    global _global_fetcher
    if _global_fetcher is None:
        # hdf5_only: 开发/测试环境akshare可能很慢，默认False（尝试akshare，超时后降级）
        _global_fetcher = FinancialFetcher(hdf5_only=hdf5_only)
    return _global_fetcher


def get_financial_history(
    stock_code: str,
    years: int = 10,
    include_derived: bool = True,
) -> pd.DataFrame:
    """
    获取单只股票近N年财务历史数据
    ============================

    示例：
        df = get_financial_history("002014", years=10)
        print(df[['statDate','revenue','roe','net_cash_ratio']].to_string())

    Returns
    -------
    pd.DataFrame
        包含以下列（若数据源提供）：
        - statDate: 财报期末
        - pubDate: 公告日期（用于判断数据可用性）
        - revenue: 营业收入
        - net_profit: 净利润
        - total_assets: 总资产
        - equity: 股东权益
        - operating_cf: 经营现金流
        - roe: 净资产收益率
        - roic: 投资资本回报率（计算）
        - net_margin: 净利率（计算）
        - asset_turnover: 资产周转率（计算）
        - equity_multiplier: 权益乘数（计算）
        - net_cash_ratio: 净现比（计算）
        - cfo_quality: 现金流质量
        - data_source: 数据来源
        - gaap_breakpoint: 会计准则标注
    """
    fetcher = get_fetcher()
    df = fetcher.fetch(stock_code, years=years)

    if df.empty:
        return df

    if include_derived:
        # 只对akshare数据计算衍生指标（HDF5列名不标准）
        ak_rows = df[df.get('data_source', pd.Series(['akshare'])) == 'akshare']
        if not ak_rows.empty:
            df = compute_all_metrics(df)

    return df


def get_derived_metrics(stock_code: str, year: Optional[str] = None) -> Dict:
    """
    获取特定年份的衍生指标（用于下游模块）
    ======================================

    Parameters
    ----------
    stock_code : str
        股票代码
    year : str, optional
        年份，如 '2023'。若为None，返回最新一期。

    Returns
    -------
    Dict
        包含 roic, roe_vs_wacc, dupont, cfo_quality, net_cash_ratio
    """
    df = get_financial_history(stock_code, years=10, include_derived=True)

    if df.empty:
        return {}

    if year:
        df = df[df['statDate'].str.startswith(str(year))]
        if df.empty:
            return {}

    row = df.iloc[-1]  # 取最新一期

    result = {
        "stock_code": stock_code,
        "stat_date": str(row.get("statDate", "")),
        "pub_date": str(row.get("pubDate", "")),
        "data_source": row.get("data_source", "unknown"),
    }

    # ROE vs WACC
    roe_val = row.get("roe", row.get("net_margin", np.nan))
    if pd.notna(roe_val):
        result["roe_vs_wacc"] = roe_vs_wacc(float(roe_val))

    # 净现比
    ncr = row.get("net_cash_ratio")
    if pd.notna(ncr):
        result["net_cash_ratio"] = float(ncr)
        result["cfo_quality"] = row.get("cfo_quality", "unknown")

    # ROIC
    roic = row.get("roic")
    if pd.notna(roic):
        result["roic"] = float(roic)

    # 杜邦
    dupont = dupont_from_components(
        net_profit=row.get("net_profit", 0),
        revenue=row.get("revenue", 0),
        total_assets=row.get("total_assets", 0),
        equity=row.get("equity", 0),
    )
    result["dupont"] = dupont

    return result


def get_revenue_history(stock_code: str, years: int = 10) -> pd.DataFrame:
    """获取营收历史（简化接口）"""
    df = get_financial_history(stock_code, years=years)
    if df.empty:
        return df
    cols = ['statDate', 'revenue', 'revenue_growth', 'net_profit', 'profit_growth', 'data_source']
    available = [c for c in cols if c in df.columns]
    return df[available]


def get_roe_history(stock_code: str, years: int = 10) -> pd.DataFrame:
    """获取ROE历史（简化接口）"""
    df = get_financial_history(stock_code, years=years)
    if df.empty:
        return df
    cols = ['statDate', 'roe', 'roic', 'data_source']
    available = [c for c in cols if c in df.columns]
    return df[available]


def get_cfo_history(stock_code: str, years: int = 10) -> pd.DataFrame:
    """获取现金流历史（简化接口）"""
    df = get_financial_history(stock_code, years=years)
    if df.empty:
        return df
    cols = ['statDate', 'operating_cf', 'net_profit', 'net_cash_ratio', 'cfo_quality', 'data_source']
    available = [c for c in cols if c in df.columns]
    return df[available]
