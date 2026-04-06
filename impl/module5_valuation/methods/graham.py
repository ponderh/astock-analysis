"""
graham.py: 格雷厄姆数（安全边际测试，结构性隔离）
==================================================
协议要求：
  1. is_safety_test = True（明确这是安全测试，不是估值锚）
  2. verdict双轨：overall_verdict不含格雷厄姆，graham_verdict独立输出
  3. 综合信号权重 = 0（默认排除）
  4. 使用原版22.5系数（不修正）

格雷厄姆数公式（原版）：
  V = √(22.5 × EPS × BPS)
  V = √22.5 × √(EPS × BPS)

安全边际判断：
  - 安全：当前股价 < 格雷厄姆数（安全边际 > 0）
  - 不安全：当前股价 > 格雷厄姆数
"""

from __future__ import annotations

import os
import sys
import signal
import warnings
import logging
from typing import Optional, Dict, Any, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

AKSHARE_TIMEOUT = 60


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("Graham fetch timeout")


# ── 格雷厄姆数系数（原版，不修正）───────────────────────────────────────────
GRAHAM_COEFFICIENT = 22.5  # 原版系数


# ── 数据获取 ────────────────────────────────────────────────────────────────

def _get_eps_bps(stock_code: str) -> Dict[str, float]:
    """
    获取EPS和BPS（用于格雷厄姆数计算）
    直接使用akshare（慢速但数据完整），不使用module2（数据合并有bug）
    """
    code_6d = stock_code.strip()[-6:]

    # akshare financial analysis indicator（直接获取，不用module2合并）
    try:
        import akshare as ak

        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(AKSHARE_TIMEOUT)
        try:
            df = ak.stock_financial_analysis_indicator(
                symbol=code_6d,
                start_year=str(2020),
            )
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

        if df is not None and not df.empty:
            # 按日期排序，取最新一期
            date_col = df.columns[0]  # '日期'
            df = df.sort_values(date_col).dropna(subset=[date_col])

            eps = None
            bps = None

            for _, row in df.sort_values(date_col, ascending=False).iterrows():
                if eps is None:
                    for col in ["摊薄每股收益(元)", "基本每股收益(元)"]:
                        if col in row.index and pd.notna(row[col]):
                            v = float(row[col])
                            if v > 0:
                                eps = v
                                break
                if bps is None:
                    for col in ["每股净资产_调整前(元)", "每股净资产_调整后(元)"]:
                        if col in row.index and pd.notna(row[col]):
                            v = float(row[col])
                            if v > 0:
                                bps = v
                                break
                if eps and bps:
                    return {"eps": eps, "bps": bps, "source": "akshare"}

    except Exception:
        pass

    return {"eps": None, "bps": None, "source": "none"}


# ── 格雷厄姆数计算 ──────────────────────────────────────────────────────────

def compute_graham_number(
    eps: float,
    bps: float,
    coefficient: float = GRAHAM_COEFFICIENT,
) -> Optional[float]:
    """
    计算格雷厄姆数

    V = √(22.5 × EPS × BPS)

    Parameters
    ----------
    eps : float
        每股收益（TTM或最新）
    bps : float
        每股净资产
    coefficient : float
        系数（默认22.5，原版）

    Returns
    -------
    float or None
        格雷厄姆内在价值（元/股）
    """
    if not eps or not bps:
        return None

    if eps <= 0 or bps <= 0:
        return None

    # 格雷厄姆数 = sqrt(22.5 * EPS * BPS)
    v = (coefficient * eps * bps) ** 0.5

    return round(v, 2)


def compute_safety_margin(
    graham_number: float,
    current_price: float,
) -> Dict[str, Any]:
    """
    计算安全边际

    安全边际 = (格雷厄姆数 - 当前价) / 当前价 × 100%

    Returns
    -------
    Dict with safety_margin_pct, safety_passed, verdict
    """
    if not graham_number or not current_price or current_price <= 0:
        return {
            "safety_margin_pct": None,
            "safety_passed": False,
            "verdict": "数据不足",
        }

    margin_pct = (graham_number - current_price) / current_price * 100
    passed = current_price < graham_number

    if passed:
        verdict = "安全边际充足"
    elif margin_pct > -20:
        verdict = "轻微高估"
    elif margin_pct > -50:
        verdict = "明显高估"
    else:
        verdict = "严重高估"

    return {
        "safety_margin_pct": round(margin_pct, 2),
        "safety_passed": passed,
        "verdict": verdict,
    }


# ── 主入口函数 ──────────────────────────────────────────────────────────────

def analyze_graham(
    stock_code: str,
    current_price: Optional[float] = None,
    get_financial_data: bool = True,
    is_safety_test: bool = True,
) -> Dict[str, Any]:
    """
    格雷厄姆数分析（安全测试模式）

    协议要求：
      1. is_safety_test = True（明确标记为安全测试）
      2. verdict双轨：graham_verdict 独立输出
      3. 综合信号权重 = 0（默认排除）

    Parameters
    ----------
    stock_code : str
        6位股票代码
    current_price : float, optional
        当前股价
    get_financial_data : bool
        是否从akshare获取财务数据
    is_safety_test : bool
        固定为True，标记这是安全测试而非估值锚

    Returns
    -------
    Dict matching GrahamResult dataclass fields
    """
    eps = None
    bps = None

    if get_financial_data:
        data = _get_eps_bps(stock_code)
        eps = data.get("eps")
        bps = data.get("bps")

    graham_number = None
    if eps and bps:
        graham_number = compute_graham_number(eps, bps)

    # 安全边际计算
    safety_info = {
        "safety_margin_pct": None,
        "safety_passed": False,
        "verdict": "数据不足",
    }

    if graham_number is not None and current_price:
        safety_info = compute_safety_margin(graham_number, current_price)

    return {
        "graham_number": graham_number,
        "is_safety_test": is_safety_test,  # 固定True，标记为安全测试
        "current_price": current_price,
        "safety_margin_pct": safety_info["safety_margin_pct"],
        "safety_passed": safety_info["safety_passed"],
        "verdict": safety_info["verdict"],
        "eps_ttm": eps,
        "bps": bps,
        "formula_version": "original_22.5",  # 原版，不修正
        "included_in_overall": False,  # 默认不纳入综合信号
        "note": "格雷厄姆数仅用于安全边际测试，is_safety_test=True，综合信号默认排除",
    }


# ── 批量格雷厄姆分析 ───────────────────────────────────────────────────────

def analyze_graham_batch(
    stocks: list,  # [(stock_code, current_price), ...]
) -> Dict[str, Dict[str, Any]]:
    """
    批量格雷厄姆分析
    """
    results = {}
    for code, price in stocks:
        results[code] = analyze_graham(code, current_price=price)
    return results
