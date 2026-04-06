"""
api.py: 行业阈值数据库对外API
===========================
"""

from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd

from .fetcher import (
    IndustryThresholdFetcher,
    FALLBACK_THRESHOLDS,
    fetch_sw1_industry_list,
)
from .combos import check_combo_flags, COMBO_FLAGS

# 全局单例
_global_fetcher: Optional[IndustryThresholdFetcher] = None


def get_fetcher() -> IndustryThresholdFetcher:
    global _global_fetcher
    if _global_fetcher is None:
        _global_fetcher = IndustryThresholdFetcher()
    return _global_fetcher


def get_industry_class(stock_code: str) -> str:
    """
    获取股票对应的申万一级行业名称
    """
    fetcher = get_fetcher()
    return fetcher.get_industry_code(stock_code)


def get_threshold(
    industry: str,
    indicator: str,
    percentile: Optional[int] = None,
) -> Dict:
    """
    获取某行业的某指标阈值
    ======================

    示例：
        # 获取医药生物行业净现比P10分位数（红旗阈值）
        result = get_threshold("医药生物", "CFO_TO_REVENUE", percentile=10)
        print(result)
        # {'p10': 0.50, 'p50': 0.85, 'red_flag': 0.40, 'confidence': 'medium', 'source': '...'}

    Parameters
    ----------
    industry : str
        行业名称（如"医药生物"）
    indicator : str
        指标代码，支持：
        - CFO_TO_REVENUE（净现比）
        - ROE（净资产收益率）
        - REVENUE_GROWTH（营收增速）
        - GROSS_MARGIN（毛利率）
        - DEBT_RATIO（资产负债率）
        - NET_MARGIN（净利率）
        - AR_GROWTH（应收增速）

    percentile : int, optional
        指定分位数（5/10/25/50/75/90/95）
        若为None，返回完整分位数表

    Returns
    -------
    Dict
        包含：{分位数key: 值, red_flag, flag_direction, confidence, source}
    """
    fetcher = get_fetcher()
    thresholds = fetcher.get_thresholds(industry, indicator)

    if percentile is None:
        return thresholds

    # 返回指定分位数
    pkey = f"p{percentile}" if percentile in [5, 10, 25, 50, 75, 90, 95] else f"p50"
    return {
        "industry": industry,
        "indicator": indicator,
        "percentile": percentile,
        "value": thresholds.get(pkey, thresholds.get("p50")),
        "red_flag": thresholds.get("red_flag"),
        "flag_direction": thresholds.get("flag_direction", "lt"),
        "confidence": thresholds.get("confidence", "low"),
        "source": thresholds.get("source", "unknown"),
    }


def get_red_flags(
    stock_code: str,
    financial_data: pd.DataFrame,
    report_date: Optional[str] = None,
) -> List[Dict]:
    """
    获取某只股票的所有红旗信号
    ==========================

    对每项指标，与行业阈值对比，判断是否触发红旗

    示例：
        df = get_financial_history("002014")
        flags = get_red_flags("002014", df, report_date="2024-12-31")
        for f in flags:
            print(f"{f['indicator']}: actual={f['actual']}, threshold={f['threshold']}, severity={f['severity']}")

    Parameters
    ----------
    stock_code : str
        股票代码
    financial_data : pd.DataFrame
        来自 module2_financial 的财务数据
    report_date : str, optional
        报表日期（如"2024-12-31"）

    Returns
    -------
    List[Dict]
        [{indicator, actual, threshold, gap, severity, module}, ...]
    """
    if financial_data.empty:
        return []

    # 获取行业分类
    industry = get_industry_class(stock_code)

    # 指标映射：财务数据列名 → 阈值指标代码
    INDICATOR_MAP = {
        "net_cash_ratio": "CFO_TO_REVENUE",
        "roe": "ROE",
        "revenue_growth": "REVENUE_GROWTH",
        "gross_margin": "GROSS_MARGIN",
        "debt_ratio": "DEBT_RATIO",
        "net_margin": "NET_MARGIN",
    }

    # 筛选最新一期数据
    if report_date:
        df = financial_data[financial_data['statDate'] == report_date]
    else:
        df = financial_data.sort_values('statDate').tail(2)

    if df.empty:
        return []

    latest = df.iloc[-1]
    flags = []

    for col, ind_code in INDICATOR_MAP.items():
        if col not in latest.index:
            continue

        actual = latest[col]
        if pd.isna(actual):
            continue

        threshold_data = get_threshold(industry, ind_code)
        red_flag = threshold_data.get("red_flag")
        if red_flag is None:
            continue

        flag_direction = threshold_data.get("flag_direction", "lt")

        # 判断是否触发红旗
        if flag_direction == "lt":
            triggered = actual < red_flag
        elif flag_direction == "gt":
            triggered = actual > red_flag
        else:
            triggered = False

        # 计算偏离度
        gap = (actual - red_flag) / abs(red_flag) if red_flag != 0 else np.nan

        severity = "RED" if triggered else "GREEN"

        flags.append({
            "stock_code": stock_code,
            "industry": industry,
            "stat_date": str(latest.get("statDate", "")),
            "indicator": ind_code,
            "actual": float(actual),
            "threshold": float(red_flag),
            "gap": float(gap) if not np.isnan(gap) else None,
            "severity": severity,
            "module": "模块3/4: 盈利质量",
            "confidence": threshold_data.get("confidence", "low"),
            "source": threshold_data.get("source", ""),
        })

    # 三大危险信号组合
    combo_result = check_combo_flags(financial_data)
    if combo_result["red_count"] > 0:
        for detail in combo_result["details"]:
            if detail.get("triggered"):
                flags.append({
                    "stock_code": stock_code,
                    "industry": industry,
                    "stat_date": str(latest.get("statDate", "")),
                    "indicator": f"COMBO:{detail['combo_id']}",
                    "actual": None,
                    "threshold": None,
                    "gap": None,
                    "severity": detail.get("severity", "RED"),
                    "module": detail.get("module", "模块3/4"),
                    "combo_name": detail.get("name", ""),
                    "confidence": "high",  # 组合逻辑比单指标更可靠
                })

    return flags


def check_combo_flags_summary(
    stock_code: str,
    financial_data: pd.DataFrame,
) -> Dict:
    """
    检查三大危险信号组合（简化入口）
    ================================
    """
    industry = get_industry_class(stock_code)
    result = check_combo_flags(financial_data)
    result["industry"] = industry
    result["stock_code"] = stock_code
    return result


# ============================================================
# 申万行业列表
# ============================================================

def list_sw1_industries() -> List[str]:
    """获取申万一级行业名称列表"""
    return fetch_sw1_industry_list()


def list_indicators() -> List[str]:
    """获取支持的指标列表"""
    return list(FALLBACK_THRESHOLDS.keys())
