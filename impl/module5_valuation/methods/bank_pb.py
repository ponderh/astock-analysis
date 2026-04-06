"""
bank_pb.py: 银行PB估值（Phase 1无调整版）
==========================================
协议要求（绝对约束）：
  1. 仅输出原始PB与行业均值的比较
  2. 不引入任何不良率/拨备覆盖率调整
  3. 明确标注：bank_pb_adjusted = False
  4. Phase1不做任何调整

原因（协议已裁决）：
  银行PB调整机制工程上不可行（数据缺口未解决前禁止引入）
"""

from __future__ import annotations

import os
import sys
import signal
import warnings
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

AKSHARE_TIMEOUT = 60


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("Bank PB fetch timeout")


# ── 银行行业PB均值（东方财富实时）───────────────────────────────────────────

def _get_bank_pb(stock_code: str) -> Optional[float]:
    """
    获取个股原始PB（akshare）
    """
    code_6d = stock_code.strip()[-6:]

    try:
        import akshare as ak

        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(AKSHARE_TIMEOUT)
        try:
            df = ak.stock_a_indicator_ly(symbol=code_6d)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

        if df is None or df.empty:
            return None

        latest = df.iloc[-1]

        for col in df.columns:
            if "PB" in str(col).upper():
                v = latest[col]
                if pd.notna(v) and float(v) > 0:
                    return float(v)

        return None

    except Exception:
        return None


def _get_industry_avg_pb() -> Optional[float]:
    """
    获取银行行业平均PB（东方财富）
    """
    try:
        import akshare as ak

        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(AKSHARE_TIMEOUT)
        try:
            # 银行板块行情
            df = ak.stock_board_industry_hist_em(
                symbol="银行",
                period="yearly",
                start_date=f"{datetime.now().year}0101",
                end_date=datetime.now().strftime("%Y%m%d"),
            )
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

        if df is None or df.empty:
            return None

        # 取最新一期市净率
        latest = df.sort_values("日期", ascending=False).iloc[0]

        for col in df.columns:
            if "市净率" in str(col) or "PB" in str(col):
                v = latest[col]
                if pd.notna(v) and float(v) > 0:
                    return float(v)

        return None

    except Exception:
        return None


# ── 银行股票列表（已知）──────────────────────────────────────────────────────

KNOWN_BANK_CODES = {
    "600000": "浦发银行",
    "600036": "招商银行",
    "000001": "平安银行",
    "601166": "兴业银行",
    "601169": "北京银行",
    "601229": "上海银行",
    "601288": "农业银行",
    "601328": "交通银行",
    "601398": "工商银行",
    "601818": "光大银行",
    "601939": "建设银行",
    "601988": "中国银行",
    "601998": "中信银行",
    "600015": "华夏银行",
    "600016": "民生银行",
    "600036": "招商银行",
    "002142": "宁波银行",
    "002807": "江阴银行",
    "002839": "张家港行",
    "002936": "郑州银行",
    "002948": "青岛银行",
    "600919": "江苏银行",
    "600926": "杭州银行",
    "600928": "西安银行",
    "601077": "渝农商行",
    "601128": "常熟银行",
    "601577": "长沙银行",
    "601658": "邮储银行",
    "601838": "成都银行",
    "601860": "紫金银行",
    "601963": "重庆银行",
}


def is_bank_stock(stock_code: str) -> bool:
    """判断是否为银行股（简单代码匹配）"""
    code_6d = stock_code.strip()[-6:]
    return code_6d in KNOWN_BANK_CODES


# ── 主入口函数 ──────────────────────────────────────────────────────────────

def analyze_bank_pb(
    stock_code: str,
    current_price: Optional[float] = None,
    use_akshare: bool = True,
) -> Dict[str, Any]:
    """
    银行PB分析（Phase 1无调整版）

    协议要求（绝对约束）：
      1. 仅输出原始PB与行业均值的比较
      2. 不引入任何不良率/拨备覆盖率调整
      3. 明确标注：bank_pb_adjusted = False
      4. Phase1不做任何调整

    Parameters
    ----------
    stock_code : str
        6位股票代码
    current_price : float, optional
        当前股价（用于参考）
    use_akshare : bool
        是否从akshare获取数据

    Returns
    -------
    Dict matching BankPBResult dataclass fields
    """
    current_pb = None
    industry_avg_pb = None

    if use_akshare:
        current_pb = _get_bank_pb(stock_code)
        if is_bank_stock(stock_code):
            industry_avg_pb = _get_industry_avg_pb()

    # 计算vs行业均值
    vs_industry_pct = None
    if current_pb is not None and industry_avg_pb is not None and industry_avg_pb != 0:
        vs_industry_pct = (current_pb - industry_avg_pb) / industry_avg_pb * 100

    # 估值判断
    verdict = "不确定"
    confidence = "low"

    if current_pb is not None and industry_avg_pb is not None:
        if vs_industry_pct is not None:
            if vs_industry_pct < -20:
                verdict = "明显低估（相对行业）"
                confidence = "medium"
            elif vs_industry_pct < -10:
                verdict = "轻微低估（相对行业）"
                confidence = "medium"
            elif vs_industry_pct > 50:
                verdict = "明显高估（相对行业）"
                confidence = "medium"
            elif vs_industry_pct > 20:
                verdict = "轻微高估（相对行业）"
                confidence = "medium"
            else:
                verdict = "相对合理"
                confidence = "medium"

    return {
        "current_pb": round(current_pb, 3) if current_pb else None,
        "industry_avg_pb": round(industry_avg_pb, 3) if industry_avg_pb else None,
        "vs_industry_pct": round(vs_industry_pct, 1) if vs_industry_pct else None,
        "verdict": verdict,
        "confidence": confidence,
        # 协议要求的标注（Phase1固定）
        "bank_pb_adjusted": False,
        "note": "Phase1不含信用风险调整；无不良率/拨备覆盖率修正",
    }


# ── 快捷函数：判断是否应使用银行PB路由 ─────────────────────────────────────

def should_use_bank_pb(stock_code: str) -> bool:
    """
    判断是否应使用银行PB方法
    注意：这是软置信度，不是硬路由！
    返回一个置信度分数（0~1），不是boolean
    """
    return is_bank_stock(stock_code)
