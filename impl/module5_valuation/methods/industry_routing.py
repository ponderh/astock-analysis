"""
industry_routing.py: 行业置信度软路由
======================================
协议要求（绝对禁止）：
  - 禁止硬路由：if bank → pb_only
  - 禁止单一行业代码直接路由到单一方法

必须实现：
  1. 行业置信度评分：get_industry_confidence(stock_code) → 0~1
  2. 多业务加权：主营构成比例 × 各行业阈值
  3. 当置信度 < 0.6 时，industry_flag = "low_confidence"，所有行业调整结果降权50%
  4. 软置信度：多方法加权输出，不硬拦截
"""

from __future__ import annotations

import os
import sys
import signal
import warnings
import logging
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

AKSHARE_TIMEOUT = 15


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("Industry routing timeout")


# ── 已知股票行业映射 ───────────────────────────────────────────────────────

STOCK_INDUSTRY_MAP = {
    "002014": "医药生物",    # 永新股份
    "600036": "银行",         # 招商银行
    "601318": "非银金融",    # 中国平安
    "600519": "食品饮料",    # 贵州茅台
    "000858": "食品饮料",    # 五粮液
    "600000": "银行",         # 浦发银行
    "000001": "银行",         # 平安银行
    "600518": "医药生物",    # 康美药业
    "000651": "家用电器",    # 格力电器
    "600104": "汽车",         # 上汽集团
    "601888": "休闲服务",    # 中国中免
    "002475": "电子",         # 立讯精密
    "300750": "电气设备",    # 宁德时代
    "600276": "医药生物",    # 恒瑞医药
    "688981": "半导体",      # 中芯国际
}


# ── 主营构成数据 ────────────────────────────────────────────────────────────

def _get_business_mix(stock_code: str) -> Dict[str, float]:
    """
    获取股票主营构成（行业占比）
    从akshare获取，若失败则用已知映射

    Returns
    Dict[行业名, 占比（0~1）]
    """
    code_6d = stock_code.strip()[-6:]

    # 已知主营构成（占位符，真实场景用akshare）
    KNOWN_MIX = {
        "002014": {"医药生物": 1.0},
        "600036": {"银行": 1.0},
        "601318": {"非银金融": 0.70, "银行": 0.20, "房地产": 0.10},
        "600519": {"食品饮料": 1.0},
        "000858": {"食品饮料": 1.0},
        "600000": {"银行": 1.0},
        "000001": {"银行": 1.0},
        "600518": {"医药生物": 0.80, "商业贸易": 0.20},
        "000651": {"家用电器": 1.0},
    }

    if code_6d in KNOWN_MIX:
        return KNOWN_MIX[code_6d]

    # 尝试akshare
    try:
        import akshare as ak

        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(AKSHARE_TIMEOUT)
        try:
            df = ak.stock_zyjs_ths(symbol=code_6d)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

        if df is not None and not df.empty:
            result = {}
            for _, row in df.iterrows():
                # 取行业和占比列
                industry = None
                ratio = None
                for col in df.columns:
                    if "行" in str(col) or "业" in str(col):
                        industry = str(row[col]).strip()
                    if "比" in str(col) or "占" in str(col):
                        try:
                            ratio = float(str(row[col]).replace("%", "")) / 100.0
                        except Exception:
                            ratio = None
                if industry and ratio and ratio > 0:
                    result[industry] = ratio
            if result:
                return result

    except Exception:
        pass

    # Fallback：单行业
    primary = STOCK_INDUSTRY_MAP.get(code_6d, "未知")
    return {primary: 1.0}


# ── 行业置信度计算 ──────────────────────────────────────────────────────────

def get_industry_confidence(
    stock_code: str,
    business_mix: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    计算行业置信度（软路由核心）

    协议要求：
      1. 置信度评分：0~1
      2. 多业务加权：主营构成比例 × 各行业阈值
      3. 置信度 < 0.6 → industry_flag = "low_confidence"，降权50%
      4. 禁止硬路由

    Returns
    -------
    Dict with fields matching IndustryConfidence dataclass
    """
    code_6d = stock_code.strip()[-6:]

    # 获取主营构成
    if business_mix is None:
        business_mix = _get_business_mix(code_6d)

    if not business_mix:
        return {
            "stock_code": code_6d,
            "primary_industry": "未知",
            "confidence_score": 0.0,
            "business_mix": {},
            "sw3_industry": "",
            "sw2_industry": "",
            "routing_method": "fallback",
            "is_low_confidence": True,
            "note": "无法获取行业分类，置信度=0",
        }

    # 主行业（占比最大的）
    primary_industry = max(business_mix, key=business_mix.get)
    primary_ratio = business_mix.get(primary_industry, 0)

    # 置信度评分逻辑
    # 多业务（>2个主营行业）→ 降低置信度
    n_businesses = len([k for k, v in business_mix.items() if v >= 0.1])

    if n_businesses == 1:
        # 单一主业 → 高置信度
        confidence_score = min(1.0, primary_ratio)
        routing_method = "single"
    elif n_businesses <= 3:
        # 2-3个主业 → 中置信度
        confidence_score = min(0.8, primary_ratio * 0.9)
        routing_method = "multi"
    else:
        # 多元化 → 低置信度
        confidence_score = min(0.6, primary_ratio * 0.7)
        routing_method = "diversified"

    # 检查是否有跨行业业务（需要多方法加权）
    is_cross_industry = n_businesses > 1

    # 置信度 < 0.6 → 低置信度降权标志
    is_low_confidence = confidence_score < 0.6

    return {
        "stock_code": code_6d,
        "primary_industry": primary_industry,
        "confidence_score": round(confidence_score, 3),
        "business_mix": {k: round(v, 3) for k, v in business_mix.items()},
        "sw3_industry": "",  # SW3需要额外查询
        "sw2_industry": "",  # SW2需要额外查询
        "routing_method": routing_method,
        "is_low_confidence": is_low_confidence,
        "effective_weight_multiplier": 0.5 if is_low_confidence else 1.0,
        "is_cross_industry": is_cross_industry,
        "note": f"{routing_method}, 置信度={confidence_score:.2f}",
    }


# ── 行业阈值加权（多方法加权输出）───────────────────────────────────────────

def compute_industry_weighted_threshold(
    stock_code: str,
    indicator: str,
    business_mix: Optional[Dict[str, float]] = None,
    industry_thresholds_getter=None,  # 函数: (industry, indicator, percentile) → threshold
) -> Dict[str, Any]:
    """
    多行业加权阈值计算（软路由核心）

    当股票跨多个行业时，按主营构成比例加权各行业阈值

    示例：
      中国平安：70%非银金融 + 20%银行 + 10%房地产
      → PB阈值 = 0.7 × 非银PB_P20 + 0.2 × 银行PB_P20 + 0.1 × 地产PB_P20

    Parameters
    ----------
    industry_thresholds_getter : callable, optional
        获取行业阈值的函数，签名为 (industry, indicator, percentile) → value
        若为None，使用内置的FALLBACK阈值

    Returns
    -------
    Dict with weighted_threshold, component_thresholds, weighting_method
    """
    code_6d = stock_code.strip()[-6:]

    if business_mix is None:
        business_mix = _get_business_mix(code_6d)

    # 内置Fallback阈值（极简化）
    def default_getter(industry, indicator, percentile):
        FALLBACK_PB = {
            "银行": {"p20": 0.5, "p50": 0.7, "p80": 1.0},
            "非银金融": {"p20": 0.8, "p50": 1.2, "p80": 2.0},
            "医药生物": {"p20": 2.0, "p50": 3.5, "p80": 5.5},
            "食品饮料": {"p20": 4.0, "p50": 6.0, "p80": 9.0},
            "家用电器": {"p20": 1.5, "p50": 2.5, "p80": 4.0},
            "电子": {"p20": 2.0, "p50": 3.0, "p80": 5.0},
            "房地产": {"p20": 0.4, "p50": 0.8, "p80": 1.5},
        }
        pkey = f"p{percentile}"
        return FALLBACK_PB.get(industry, {}).get(pkey, 2.0)

    getter = industry_thresholds_getter or default_getter

    # 加权计算
    weighted_threshold = 0.0
    total_weight = 0.0
    component_thresholds = {}

    for industry, ratio in business_mix.items():
        if ratio < 0.05:
            continue

        threshold = getter(industry, indicator, percentile=20)
        component_thresholds[industry] = {
            "ratio": ratio,
            "threshold": threshold,
            "weighted": threshold * ratio,
        }
        weighted_threshold += threshold * ratio
        total_weight += ratio

    if total_weight > 0:
        weighted_threshold /= total_weight

    return {
        "weighted_threshold": round(weighted_threshold, 3),
        "component_thresholds": component_thresholds,
        "weighting_method": "revenue_proportional",
        "total_industries": len(component_thresholds),
        "note": f"按主营构成比例加权（{len(component_thresholds)}个行业）",
    }
