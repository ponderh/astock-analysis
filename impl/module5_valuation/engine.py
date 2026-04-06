"""
engine.py: 估值分析引擎 — 核心串联逻辑
======================================
整合所有估值方法，按P1-1协议输出结构化估值报告。

调用流程:
    ValuationEngine.analyze(stock_code) → ValuationBlock → JSON报告

协议约束（绝对红线，禁止违反）：
  1. DCF必须输出三档（乐观/基准/悲观），非点估计
  2. 格雷厄姆数：is_safety_test=True，默认排除出综合信号
  3. 银行PB：Phase1不做任何调整
  4. 历史分位：必须打regime标签，默认使用注册制后数据
  5. 行业路由：软置信度，禁止硬拦截
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
import warnings
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import pandas as pd

# 抑制第三方库噪音
for _lib in ["urllib3", "requests", "PIL", "matplotlib"]:
    logging.getLogger(_lib).setLevel(logging.WARNING)
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

# ── 路径配置 ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMPL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# ── 股票名称映射 ─────────────────────────────────────────────────────────
STOCK_NAMES: Dict[str, str] = {
    "002014": "永新股份",
    "600518": "康美药业",
    "600036": "招商银行",
    "601318": "中国平安",
    "600519": "贵州茅台",
    "000858": "五粮液",
    "000001": "平安银行",
    "600000": "浦发银行",
    "000651": "格力电器",
}


def get_stock_name(stock_code: str) -> str:
    code_6d = stock_code.strip()[-6:]
    return STOCK_NAMES.get(code_6d, code_6d)


# ── 方法权重配置 ─────────────────────────────────────────────────────────

# 默认权重配置（可调整）
DEFAULT_WEIGHTS = {
    "pe_pb_percentile": 0.40,  # PE/PB分位（主锚）
    "dcf": 0.20,               # DCF三档（辅助）
    "graham": 0.00,            # 格雷厄姆（默认=0，安全测试）
    "bank_pb": 0.30,           # 银行PB（Phase1无调整）
}


# ── 延迟导入 ──────────────────────────────────────────────────────────────

def _import_industry_thresholds():
    """延迟导入行业阈值"""
    sys.path.insert(0, IMPL_DIR)
    from industry_thresholds.api import get_threshold, get_industry_class
    return get_threshold, get_industry_class


def _import_current_price():
    """延迟导入实时行情获取"""
    sys.path.insert(0, IMPL_DIR)
    try:
        from module2_financial.api import get_current_price
        return get_current_price
    except ImportError:
        return None


def _import_module2():
    """延迟导入module2"""
    sys.path.insert(0, IMPL_DIR)
    from module2_financial.api import get_financial_history, get_derived_metrics
    return get_financial_history, get_derived_metrics


# ── 实时价格获取 ─────────────────────────────────────────────────────────

def _get_current_price(stock_code: str) -> Optional[float]:
    """获取当前股价（akshare实时）"""
    code_6d = stock_code.strip()[-6:]

    try:
        import akshare as ak

        def handler(signum, frame):
            raise TimeoutError("price timeout")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(10)

        try:
            df = ak.stock_bid_ask_em(symbol=code_6d)
            if df is not None and not df.empty:
                for col in df.columns:
                    if "买" in str(col) or "最新" in str(col) or "现价" in str(col):
                        v = df.iloc[0][col]
                        if v and float(v) > 0:
                            signal.alarm(0)
                            return float(v)
            # Fallback
            df2 = ak.stock_zh_a_spot_em()
            if df2 is not None and not df2.empty:
                row = df2[df2["代码"] == code_6d]
                if not row.empty:
                    v = row.iloc[0].get("最新价")
                    if v and float(v) > 0:
                        signal.alarm(0)
                        return float(v)
        finally:
            signal.alarm(0)

    except Exception:
        pass

    return None


# ── PE/PB分位（regime-aware） ────────────────────────────────────────────

def _compute_pe_pb_percentile(
    stock_code: str,
    industry_name: str,
    indicator: str = "PB",
    current_value: Optional[float] = None,
) -> Dict[str, Any]:
    """计算PE/PB历史分位（regime-aware）"""
    try:
        sys.path.insert(0, os.path.join(IMPL_DIR, "module5_valuation"))
        from methods.pe_pb_percentile import get_pe_pb_percentile
        return get_pe_pb_percentile(
            stock_code=stock_code,
            industry_name=industry_name,
            indicator=indicator,
            current_value=current_value,
        )
    except Exception as e:
        logger.warning(f"PE/PB分位计算失败 [{stock_code}]: {e}")
        return {
            "percentile_full": None,
            "percentile_recent": None,
            "regime_discontinuity_warning": False,
            "threshold_p20": None,
            "threshold_p80": None,
            "confidence": "low",
            "data_years": 0,
            "n_stocks_used": 0,
            "note": f"计算失败: {e}",
        }


# ── DCF三档 ──────────────────────────────────────────────────────────────

def _compute_dcf(
    stock_code: str,
    current_price: Optional[float] = None,
) -> Dict[str, Any]:
    """计算DCF三档"""
    try:
        sys.path.insert(0, os.path.join(IMPL_DIR, "module5_valuation"))
        from methods.dcf import compute_dcf_three_scenario
        return compute_dcf_three_scenario(
            stock_code=stock_code,
            current_price=current_price,
            use_akshare=True,
        )
    except Exception as e:
        logger.warning(f"DCF计算失败 [{stock_code}]: {e}")
        return {
            "intrinsic_pessimistic": None,
            "intrinsic_central": None,
            "intrinsic_optimistic": None,
            "confidence_width_pct": None,
            "dcf_over_width_threshold": False,
            "dcf_zero_width_error": False,
            "dcf_width_zero_error": True,
            "confidence": "low",
            "current_price": current_price,
            "wacc": None,
            "perpetual_growth_rate": None,
            "note": f"DCF计算失败: {e}",
        }


# ── 格雷厄姆数 ────────────────────────────────────────────────────────────

def _compute_graham(
    stock_code: str,
    current_price: Optional[float] = None,
) -> Dict[str, Any]:
    """计算格雷厄姆数（安全测试模式）"""
    try:
        sys.path.insert(0, os.path.join(IMPL_DIR, "module5_valuation"))
        from methods.graham import analyze_graham
        return analyze_graham(
            stock_code=stock_code,
            current_price=current_price,
            get_financial_data=True,
            is_safety_test=True,  # 固定为安全测试
        )
    except Exception as e:
        logger.warning(f"格雷厄姆计算失败 [{stock_code}]: {e}")
        return {
            "graham_number": None,
            "is_safety_test": True,
            "current_price": current_price,
            "safety_margin_pct": None,
            "safety_passed": False,
            "verdict": "数据不足",
            "eps_ttm": None,
            "bps": None,
            "formula_version": "original_22.5",
            "included_in_overall": False,
            "note": f"格雷厄姆计算失败: {e}",
        }


# ── 银行PB ────────────────────────────────────────────────────────────────

def _compute_bank_pb(
    stock_code: str,
    current_price: Optional[float] = None,
) -> Dict[str, Any]:
    """计算银行PB（Phase1无调整）"""
    try:
        sys.path.insert(0, os.path.join(IMPL_DIR, "module5_valuation"))
        from methods.bank_pb import analyze_bank_pb
        return analyze_bank_pb(
            stock_code=stock_code,
            current_price=current_price,
            use_akshare=True,
        )
    except Exception as e:
        logger.warning(f"银行PB计算失败 [{stock_code}]: {e}")
        return {
            "current_pb": None,
            "industry_avg_pb": None,
            "vs_industry_pct": None,
            "verdict": "数据不足",
            "confidence": "low",
            "bank_pb_adjusted": False,
            "note": f"银行PB计算失败: {e}",
        }


# ── 行业置信度软路由 ──────────────────────────────────────────────────────

def _compute_industry_confidence(
    stock_code: str,
) -> Dict[str, Any]:
    """计算行业置信度（软路由）"""
    try:
        sys.path.insert(0, os.path.join(IMPL_DIR, "module5_valuation"))
        from methods.industry_routing import get_industry_confidence
        return get_industry_confidence(stock_code=stock_code)
    except Exception as e:
        logger.warning(f"行业置信度计算失败 [{stock_code}]: {e}")
        return {
            "stock_code": stock_code.strip()[-6:],
            "primary_industry": "未知",
            "confidence_score": 0.0,
            "business_mix": {},
            "sw3_industry": "",
            "sw2_industry": "",
            "routing_method": "fallback",
            "is_low_confidence": True,
            "note": f"行业置信度计算失败: {e}",
        }


# ── 综合信号计算 ─────────────────────────────────────────────────────────

def _compute_composite_signal(
    pb_result: Optional[Dict],
    pe_result: Optional[Dict],
    dcf_result: Optional[Dict],
    graham_result: Optional[Dict],
    bank_pb_result: Optional[Dict],
    industry_confidence: Optional[Dict],
    current_price: Optional[float],
) -> Dict[str, Any]:
    """
    计算综合信号

    协议约束：
      1. 格雷厄姆数默认权重=0（默认排除出综合信号）
      2. DCF超宽时权重归零
      3. 有效方法<2 → verdict="数据不足"
      4. 行业置信度 < 0.6 → 所有行业调整结果降权50%

    Returns
    -------
    Dict matching CompositeSignal dataclass
    """
    weights = DEFAULT_WEIGHTS.copy()
    valid_methods = 0
    regime_warning = False

    # 行业置信度降权
    weight_multiplier = 1.0
    if industry_confidence and industry_confidence.get("is_low_confidence"):
        weight_multiplier = 0.5
        logger.info("行业置信度<0.6，降权50%")

    # ── PE/PB分位 ──────────────────────────────────────────────────
    pe_pb_score = 50.0  # 基准分
    if pb_result:
        pct = pb_result.get("percentile_recent") or pb_result.get("percentile_full")
        if pct is not None:
            # PB分位：<20%为低估（score高），>80%为高估（score低）
            if pct < 20:
                pe_pb_score = min(90.0, 50.0 + (20 - pct) * 2)
            elif pct > 80:
                pe_pb_score = max(10.0, 50.0 - (pct - 80) * 2)
            else:
                pe_pb_score = 50.0 + (50 - pct) * 0.3  # 中间区域微调
            valid_methods += 1
            if pb_result.get("regime_discontinuity_warning"):
                regime_warning = True

    if pe_result and valid_methods == 0:
        pct = pe_result.get("percentile_recent") or pe_result.get("percentile_full")
        if pct is not None:
            pe_pb_score = 50.0
            valid_methods += 1

    pe_pb_score = min(100, max(0, pe_pb_score)) * weight_multiplier

    # ── DCF三档 ────────────────────────────────────────────────────
    dcf_score = 50.0
    dcf_effective_weight = weights["dcf"]
    if dcf_result:
        central = dcf_result.get("intrinsic_central")
        if central and current_price:
            # 内在价值 vs 当前价
            ratio = central / current_price
            if ratio > 1.2:
                dcf_score = min(90, 50 + (ratio - 1) * 50)
            elif ratio < 0.8:
                dcf_score = max(10, 50 - (1 - ratio) * 50)
            else:
                dcf_score = 50 + (ratio - 1) * 100

        # DCF超宽降权
        if dcf_result.get("dcf_over_width_threshold"):
            dcf_effective_weight = 0.0
            dcf_score = 50.0  # 超宽时不参与判断

        if dcf_result.get("confidence") != "low" or dcf_result.get("dcf_over_width_threshold") is False:
            valid_methods += 1

    dcf_score = min(100, max(0, dcf_score)) * dcf_effective_weight

    # ── 格雷厄姆（默认不纳入） ─────────────────────────────────────
    graham_verdict = "不确定"
    graham_included = False
    if graham_result:
        graham_verdict = graham_result.get("verdict", "不确定")
        # 仅当用户明确要求时纳入（included_in_overall=True）
        # 协议默认：included_in_overall = False

    # ── 银行PB ─────────────────────────────────────────────────────
    bank_pb_score = 0.0
    if bank_pb_result:
        pb_val = bank_pb_result.get("current_pb")
        avg_pb = bank_pb_result.get("industry_avg_pb")
        if pb_val and avg_pb:
            ratio = pb_val / avg_pb
            if ratio < 0.8:
                bank_pb_score = min(90, 50 + (0.8 - ratio) * 100)
            elif ratio > 1.2:
                bank_pb_score = max(10, 50 - (ratio - 1.2) * 100)
            else:
                bank_pb_score = 50.0
            valid_methods += 1

    bank_pb_score = min(100, max(0, bank_pb_score)) * weights["bank_pb"]

    # ── 综合分 ─────────────────────────────────────────────────────
    total_weight = weights["pe_pb_percentile"] + dcf_effective_weight + weights["bank_pb"]
    if total_weight > 0:
        overall_score = (
            pe_pb_score * weights["pe_pb_percentile"]
            + dcf_score * dcf_effective_weight
            + bank_pb_score * weights["bank_pb"]
        ) / total_weight
    else:
        overall_score = 0.0

    # ── 综合verdict ────────────────────────────────────────────────
    if valid_methods < 2:
        overall_verdict = "数据不足"
        overall_score = 0.0
    elif overall_score >= 70:
        overall_verdict = "低估"
    elif overall_score >= 55:
        overall_verdict = "合理偏低"
    elif overall_score >= 45:
        overall_verdict = "合理"
    elif overall_score >= 30:
        overall_verdict = "合理偏高"
    else:
        overall_verdict = "高估"

    # ── 质量门控 ──────────────────────────────────────────────────
    quality_gate_passed = valid_methods >= 1

    return {
        "overall_verdict": overall_verdict,
        "overall_score": round(overall_score, 1),
        "pe_pb_score": round(pe_pb_score, 1),
        "dcf_score": round(dcf_score, 1),
        "bank_pb_score": round(bank_pb_score, 1),
        "valid_methods": valid_methods,
        "method_weights": {
            "pe_pb_percentile": weights["pe_pb_percentile"],
            "dcf": dcf_effective_weight,
            "bank_pb": weights["bank_pb"],
            "graham": 0.0,  # 默认排除
        },
        "data_source": "estimated",
        "regime_discontinuity_warning": regime_warning,
        "graham_verdict": graham_verdict,
        "graham_included": graham_included,
        "quality_gate_passed": quality_gate_passed,
    }


# ============================================================
# ValuationEngine
# ============================================================

class ValuationEngine:
    """
    估值分析引擎
    ============

    示例:
        engine = ValuationEngine()
        result = engine.analyze("002014")
        print(result.summary())
    """

    def __init__(
        self,
        timeout_per_source: int = 20,
        use_mda: bool = False,
    ):
        self.timeout = timeout_per_source
        self.use_mda = use_mda

    def analyze(
        self,
        stock_code: str,
        report_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        对单只股票进行完整的估值分析

        Parameters
        ----------
        stock_code : str
            股票代码（支持多种格式）
        report_date : str, optional
            报告日期

        Returns
        -------
        Dict matching ValuationBlock.to_dict()
        """
        start_time = time.time()
        code_6d = stock_code.strip()[-6:]
        stock_name = get_stock_name(code_6d)
        report_date = report_date or date.today().isoformat()

        logger.info(f"[{code_6d}] 开始估值分析 | {stock_name}")

        # ── Step 1: 获取当前价格 ────────────────────────────────────
        current_price = _get_current_price(code_6d)
        logger.info(f"[{code_6d}] 当前价格: {current_price}")

        # ── Step 2: 行业置信度（软路由） ───────────────────────────
        ind_conf = _compute_industry_confidence(code_6d)
        primary_industry = ind_conf.get("primary_industry", "未知")
        logger.info(f"[{code_6d}] 行业: {primary_industry}, 置信度: {ind_conf.get('confidence_score')}")

        # ── Step 3: PE/PB分位（regime-aware） ──────────────────────
        pb_result = None
        pe_result = None
        if primary_industry != "未知":
            # 当前值从module2获取
            current_pb = None
            current_pe = None
            try:
                get_financial_history, _ = _import_module2()
                df = get_financial_history(code_6d, years=3)
                if not df.empty:
                    latest = df.sort_values("statDate").iloc[-1]
                    for col in ["pb", "PB", "市净率"]:
                        if col in latest.index and pd.notna(latest[col]) and float(latest[col]) > 0:
                            current_pb = float(latest[col])
                            break
                    for col in ["pe_ttm", "PE_TTM", "市盈率"]:
                        if col in latest.index and pd.notna(latest[col]) and float(latest[col]) > 0:
                            current_pe = float(latest[col])
                            break
            except Exception:
                pass

            pb_result = _compute_pe_pb_percentile(
                code_6d, primary_industry, "PB", current_value=current_pb
            )
            pe_result = _compute_pe_pb_percentile(
                code_6d, primary_industry, "PE", current_value=current_pe
            )

        # ── Step 4: DCF三档 ────────────────────────────────────────
        dcf_result = _compute_dcf(code_6d, current_price)

        # ── Step 5: 格雷厄姆数（安全测试，隔离） ───────────────────
        graham_result = _compute_graham(code_6d, current_price)

        # ── Step 6: 银行PB（Phase1无调整） ─────────────────────────
        bank_pb_result = None
        try:
            from methods.bank_pb import is_bank_stock
            if is_bank_stock(code_6d):
                bank_pb_result = _compute_bank_pb(code_6d, current_price)
        except Exception:
            pass

        # ── Step 7: 综合信号（格雷厄姆默认排除） ──────────────────
        composite = _compute_composite_signal(
            pb_result=pb_result,
            pe_result=pe_result,
            dcf_result=dcf_result,
            graham_result=graham_result,
            bank_pb_result=bank_pb_result,
            industry_confidence=ind_conf,
            current_price=current_price,
        )

        # ── Step 8: 组装报告 ────────────────────────────────────────
        total_time = time.time() - start_time
        logger.info(
            f"[{code_6d}] 估值分析完成 | verdict={composite['overall_verdict']} | "
            f"score={composite['overall_score']} | 耗时: {total_time:.1f}s"
        )

        return {
            "stock_code": code_6d,
            "stock_name": stock_name,
            "report_date": report_date,
            "current_price": current_price,
            "industry_confidence": ind_conf,
            "pb_result": pb_result,
            "pe_result": pe_result,
            "dcf_result": dcf_result,
            "graham_result": graham_result,
            "bank_pb_result": bank_pb_result,
            "composite_signal": composite,
            "data_source": "akshare+module2",
        }

    def analyze_and_save(
        self,
        stock_code: str,
        report_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """分析并保存报告"""
        result = self.analyze(stock_code, report_date)

        filename = f"{stock_code.strip()[-6:]}_valuation_{date.today().isoformat()}.json"
        filepath = os.path.join(REPORTS_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"估值报告已保存: {filepath}")
        return result


# ============================================================
# 快速入口函数
# ============================================================

def analyze(
    stock_code: str,
    stock_name: Optional[str] = None,
    save: bool = False,
) -> Dict[str, Any]:
    """
    一行代码估值分析

    示例:
        result = analyze("002014", "永新股份")
        print(result["composite_signal"]["overall_verdict"])
    """
    if stock_name:
        code_6d = stock_code.strip()[-6:]
        STOCK_NAMES[code_6d] = stock_name

    engine = ValuationEngine()

    if save:
        return engine.analyze_and_save(stock_code)
    else:
        return engine.analyze(stock_code)


__all__ = [
    "ValuationEngine",
    "analyze",
    "STOCK_NAMES",
]
