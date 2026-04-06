"""
dcf.py: DCF三档估值（范围估计，非点估计）
==========================================
协议要求：
  1. 必须输出三档：乐观/基准/悲观
  2. 三档宽度 > 当前股价50% → confidence=low，权重归零
  3. 三档宽度 = 0 → 数据错误告警
  4. 正常时权重 ≤ 20%
  5. DCF是辅助方法，非主锚

DCF公式（三阶段）：
  Stage 1 (explicit forecast): Σ CF_t / (1+WACC)^t
  Stage 2 (transition): CF_n * (1+g)^n / (WACC-g) / (1+WACC)^n
  Stage 3 (terminal): 永续
"""

from __future__ import annotations

import os
import sys
import signal
import warnings
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, Tuple

import numpy as np

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

AKSHARE_TIMEOUT = 60


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("DCF fetch timeout")


# ── WACC 参数 ─────────────────────────────────────────────────────────────

# 默认WACC范围（乐观/基准/悲观）
DEFAULT_WACC_RANGE = {
    "optimistic": 0.08,    # 8%  (经营质量好，市场风险偏好高)
    "central": 0.10,       # 10% (基准)
    "pessimistic": 0.12,   # 12% (风险偏好低)
}

# 默认永续增长率范围
DEFAULT_G_RANGE = {
    "optimistic": 0.04,    # 4%
    "central": 0.025,      # 2.5%
    "pessimistic": 0.015,   # 1.5%
}

# 显式预测期年数
FORECAST_YEARS = 5

# 分红比例（A股典型）
DEFAULT_PAYOUT_RATIO = 0.30


# ── 财务数据获取 ────────────────────────────────────────────────────────────

def _get_financial_data_for_dcf(
    stock_code: str,
) -> Dict[str, Any]:
    """
    获取DCF所需财务数据
    优先使用module2（HDF5缓存），akshare作为fallback（慢速，带超时保护）
    """
    code_6d = stock_code.strip()[-6:]

    # ── 方案1：module2（HDF5缓存，快速） ────────────────────────────
    # 注意：module2有数据合并bug，EPS可能在statDate=NaN的行中，需要全量扫描
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'impl'))
        from module2_financial.api import get_financial_history
        df = get_financial_history(code_6d, years=5, include_derived=True)
        if not df.empty:
            result = {}

            # EPS/BPS/ROE: 从DataFrame末尾向前扫描（NaN statDate行可能有数据）
            eps_val = None
            bps_val = None
            roe_val = None

            try:
                for _, row in df.iloc[::-1].iterrows():
                    if eps_val is None:
                        for col in ["摊薄每股收益(元)", "基本每股收益(元)"]:
                            try:
                                if col in row.index and pd.notna(row[col]) and float(row[col]) > 0:
                                    eps_val = float(row[col])
                                    break
                            except (TypeError, ValueError):
                                pass
                    if bps_val is None:
                        for col in ["每股净资产_调整前(元)", "每股净资产_调整后(元)"]:
                            try:
                                if col in row.index and pd.notna(row[col]) and float(row[col]) > 0:
                                    bps_val = float(row[col])
                                    break
                            except (TypeError, ValueError):
                                pass
                    if roe_val is None:
                        for col in ["roe", "dupont_roe"]:
                            try:
                                if col in row.index and pd.notna(row[col]) and float(row[col]) > 0:
                                    v = float(row[col])
                                    roe_val = v / 100.0 if v > 1 else v
                                    break
                            except (TypeError, ValueError):
                                pass
                    if eps_val and bps_val and roe_val:
                        break

                if eps_val:
                    result["eps_basic"] = eps_val
                if bps_val:
                    result["bps"] = bps_val
                if roe_val:
                    result["roe"] = roe_val

                # 营收增速
                df_dated = df.dropna(subset=["statDate"])
                if not df_dated.empty:
                    for _, row in df_dated.sort_values("statDate", ascending=False).iterrows():
                        for col in ["revenue_growth", "主营业务收入增长率(%)"]:
                            try:
                                if col in row.index and pd.notna(row[col]):
                                    v = float(row[col])
                                    result["revenue_growth"] = v / 100.0 if abs(v) > 1 else v
                                    break
                            except (TypeError, ValueError):
                                pass
                        if "revenue_growth" in result:
                            break

            except Exception:
                pass  # module2数据格式异常，使用akshare

            if result.get("eps_basic"):
                return result

    except Exception:
        pass

    # module2未能获取EPS，说明数据格式异常，清空result再尝试akshare
    result = {}

    # ── 方案2：akshare（慢速，带超时） ──────────────────────────────
    try:
        import akshare as ak

        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(AKSHARE_TIMEOUT)
        try:
            df_fin = ak.stock_financial_analysis_indicator(
                symbol=code_6d,
                start_year=str(datetime.now().year - 5),
            )
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

        if df_fin is None or df_fin.empty:
            return {}

        row = df_fin.iloc[-1]
        result = {}

        # EPS：使用有数据的最新行
        eps_val = None
        bps_val = None
        roe_val = None

        for _, r in df_fin.sort_values(df_fin.columns[0], ascending=False).iterrows():
            if eps_val is None:
                for col in ["摊薄每股收益(元)", "基本每股收益(元)", "加权每股收益(元)"]:
                    if col in r.index and pd.notna(r[col]):
                        try:
                            v = float(r[col])
                            if v > 0:
                                eps_val = v
                                break
                        except (TypeError, ValueError):
                            pass
            if bps_val is None:
                for col in ["每股净资产_调整前(元)", "每股净资产_调整后(元)"]:
                    if col in r.index and pd.notna(r[col]):
                        try:
                            v = float(r[col])
                            if v > 0:
                                bps_val = v
                                break
                        except (TypeError, ValueError):
                            pass
            if roe_val is None:
                for col in ["净资产收益率(%)", "加权净资产收益率(%)", "净资产报酬率(%)"]:
                    if col in r.index and pd.notna(r[col]):
                        try:
                            v = float(r[col])
                            if v > 0:
                                roe_val = v / 100.0 if v > 1 else v
                                break
                        except (TypeError, ValueError):
                            pass
            if eps_val and bps_val and roe_val:
                break

        # 如果ROE缺失，用EPS/BPS推算
        if roe_val is None and eps_val and bps_val and bps_val > 0:
            roe_val = eps_val / bps_val

        if eps_val:
            result["eps_basic"] = eps_val
        if bps_val:
            result["bps"] = bps_val
        if roe_val:
            result["roe"] = roe_val

        return result

    except TimeoutError:
        logger.warning(f"DCF财务数据获取超时 [{stock_code}]")
        return {}
    except Exception as e:
        logger.warning(f"DCF财务数据获取失败 [{stock_code}]: {e}")
        return {}


# ── 现金流估算 ─────────────────────────────────────────────────────────────

def _estimate_cash_flows(
    eps: float,
    roe: float,
    revenue_growth: Optional[float] = None,
    payout_ratio: float = DEFAULT_PAYOUT_RATIO,
    forecast_years: int = FORECAST_YEARS,
) -> Dict[str, Any]:
    """
    估算未来现金流

    基于EPS和ROE估算：
      FCF ≈ EPS * payout_ratio + BVPS * (ROE - payout_ratio * ROE)
            ≈ EPS * payout_ratio + BVPS * ROE * (1 - payout_ratio)

    其中 BVPS = EPS / ROE（近似）

    Parameters
    ----------
    eps : float
        每股收益（最新TTM）
    roe : float
        净资产收益率（小数形式，如0.15）
    revenue_growth : float, optional
        营收增速（小数形式）
    payout_ratio : float
        分红比例（默认30%）

    Returns
    -------
    Dict with growth rates for optimistic/central/pessimistic scenarios
    """
    # 安全检查
    if eps <= 0 or roe <= 0:
        return {}

    # 每股净资产
    bps = eps / roe if roe > 0 else eps * 10

    # 基准自由现金流（= 经营现金流近似，以EPS*分红率为基础）
    base_cf = eps * payout_ratio

    # 成长阶段：CF增长 = ROE * (1 - payout_ratio) ≈ 留存收益再投资的增长
    # 这是最简单的DCF近似模型

    if revenue_growth is not None:
        # 有营收增速时，使用营收增速作为现金流增长代理
        growth_central = min(max(revenue_growth, -0.10), 0.20)  # 限制在±20%
    else:
        # 无营收增速时，使用ROE*(1-payout)作为隐含增长
        growth_central = roe * (1 - payout_ratio)

    # 三档增长率
    growth_optimistic = growth_central * 1.5  # 乐观：增速+50%
    growth_pessimistic = growth_central * 0.5  # 悲观：增速-50%
    if growth_central < 0:
        growth_optimistic = growth_central * 1.5  # 亏损扩大
        growth_pessimistic = min(0.0, growth_central * 2)  # 改善

    # 限制极端值
    growth_optimistic = min(growth_optimistic, 0.25)
    growth_pessimistic = max(growth_pessimistic, -0.15)

    # 计算各年现金流
    def project_cf(base, growth, year):
        return base * ((1 + growth) ** year)

    cfs_optimistic = [project_cf(base_cf, growth_optimistic, y) for y in range(1, forecast_years + 1)]
    cfs_central = [project_cf(base_cf, growth_central, y) for y in range(1, forecast_years + 1)]
    cfs_pessimistic = [project_cf(base_cf, growth_pessimistic, y) for y in range(1, forecast_years + 1)]

    return {
        "bps": bps,
        "base_cf": base_cf,
        "growth_optimistic": growth_optimistic,
        "growth_central": growth_central,
        "growth_pessimistic": growth_pessimistic,
        "cfs_optimistic": cfs_optimistic,
        "cfs_central": cfs_central,
        "cfs_pessimistic": cfs_pessimistic,
    }


# ── DCF 计算核心 ─────────────────────────────────────────────────────────────

def _compute_dcf_value(
    cfs: list,
    wacc: float,
    terminal_g: float,
    terminal_multiple: float = 1.0,
    forecast_years: int = FORECAST_YEARS,
) -> Dict[str, float]:
    """
    计算DCF估值

    Stage 1: Σ CF_t / (1+WACC)^t  (显式预测期)
    Stage 2: Terminal Value / (1+WACC)^n
    Terminal Value = CF_n * (1+g) / (WACC - g)

    Parameters
    ----------
    cfs : list
        每年现金流列表
    wacc : float
        加权平均资本成本
    terminal_g : float
        永续增长率
    terminal_multiple : float
        终值倍数（默认1.0）
    forecast_years : int
        预测年数

    Returns
    -------
    Dict with stage1, terminal, total_value
    """
    if wacc <= terminal_g:
        # WACC必须大于永续增长率，否则无法计算
        terminal_g = wacc - 0.01

    # Stage 1: 显式预测期现值
    stage1_pv = sum(
        cf / ((1 + wacc) ** t)
        for t, cf in enumerate(cfs, 1)
    )

    # Terminal Value
    last_cf = cfs[-1] * (1 + terminal_g)
    tv = last_cf * terminal_multiple / (wacc - terminal_g)

    # Stage 2: 终值现值
    stage2_pv = tv / ((1 + wacc) ** forecast_years)

    return {
        "stage1_pv": stage1_pv,
        "terminal_pv": stage2_pv,
        "total_value": stage1_pv + stage2_pv,
        "tv": tv,
    }


# ── 三档DCF ─────────────────────────────────────────────────────────────────

def compute_dcf_three_scenario(
    stock_code: str,
    current_price: Optional[float] = None,
    use_akshare: bool = True,
) -> Dict[str, Any]:
    """
    计算DCF三档估值（主入口）

    协议要求：
      1. 必须输出三档：乐观/基准/悲观
      2. 三档宽度 > 当前股价50% → confidence=low，权重归零
      3. 三档宽度 = 0 → 数据错误告警

    Returns
    -------
    Dict with keys matching DCFResult dataclass fields
    """
    # 获取财务数据
    fin_data = {}
    if use_akshare:
        fin_data = _get_financial_data_for_dcf(stock_code)

    eps = fin_data.get("eps_basic")
    roe = fin_data.get("roe")
    revenue_growth = fin_data.get("revenue_growth")
    bps = fin_data.get("bps")

    # 如果akshare失败，尝试从模块2获取
    if not eps or not roe:
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from module2_financial.api import get_financial_history
            df = get_financial_history(stock_code, years=5, include_derived=True)
            if not df.empty:
                latest = df.sort_values("statDate").iloc[-1]
                for col in ["eps_basic", "EPS", "基本每股收益"]:
                    if col in latest.index and pd.notna(latest[col]):
                        eps = float(latest[col])
                        break
                for col in ["roe", "ROE", "净资产收益率"]:
                    if col in latest.index and pd.notna(latest[col]):
                        roe = float(latest[col]) / 100.0 if latest[col] > 1 else float(latest[col])
                        break
                for col in ["bps", "BPS", "每股净资产"]:
                    if col in latest.index and pd.notna(latest[col]):
                        bps = float(latest[col])
                        break
        except Exception:
            pass

    # 检查必要数据
    if not eps or eps <= 0:
        return {
            "intrinsic_pessimistic": None,
            "intrinsic_central": None,
            "intrinsic_optimistic": None,
            "confidence_width_pct": None,
            "dcf_over_width_threshold": False,
            "dcf_zero_width_error": True,
            "confidence": "low",
            "current_price": current_price,
            "wacc": None,
            "perpetual_growth_rate": None,
            "note": "数据不足，无法计算DCF（EPS或ROE缺失）",
        }

    if roe is None or roe <= 0:
        roe = 0.10  # 默认10%

    # 估算现金流
    cf_data = _estimate_cash_flows(
        eps=eps,
        roe=roe,
        revenue_growth=revenue_growth,
    )

    if not cf_data:
        return {
            "intrinsic_pessimistic": None,
            "intrinsic_central": None,
            "intrinsic_optimistic": None,
            "confidence_width_pct": None,
            "dcf_over_width_threshold": False,
            "dcf_zero_width_error": True,
            "confidence": "low",
            "current_price": current_price,
            "wacc": None,
            "perpetual_growth_rate": None,
            "note": "现金流估算失败",
        }

    # 计算三档
    results = {}
    scenarios = [
        ("pessimistic", cf_data["cfs_pessimistic"], DEFAULT_WACC_RANGE["pessimistic"], DEFAULT_G_RANGE["pessimistic"]),
        ("central", cf_data["cfs_central"], DEFAULT_WACC_RANGE["central"], DEFAULT_G_RANGE["central"]),
        ("optimistic", cf_data["cfs_optimistic"], DEFAULT_WACC_RANGE["optimistic"], DEFAULT_G_RANGE["optimistic"]),
    ]

    for name, cfs, wacc, g in scenarios:
        r = _compute_dcf_value(cfs, wacc, g, forecast_years=FORECAST_YEARS)
        results[name] = r["total_value"]

    intrinsic_pessimistic = results["pessimistic"]
    intrinsic_central = results["central"]
    intrinsic_optimistic = results["optimistic"]

    # 计算宽度
    width_pct = 0.0
    if intrinsic_central and intrinsic_central > 0:
        width_pct = (intrinsic_optimistic - intrinsic_pessimistic) / intrinsic_central * 100

    # 三档宽度=0错误检测
    zero_width = (intrinsic_pessimistic == intrinsic_central == intrinsic_optimistic)

    # 宽度>50%降权
    over_width = False
    confidence = "high"
    if zero_width:
        confidence = "low"
    elif width_pct > 50.0:
        over_width = True
        confidence = "low"
    elif width_pct > 30.0:
        confidence = "medium"

    note_parts = []
    if over_width:
        note_parts.append(f"三档宽度{width_pct:.0f}%>50%，置信度降为low，权重归零")
    if current_price:
        note_parts.append(f"当前价{current_price}")

    return {
        "intrinsic_pessimistic": round(intrinsic_pessimistic, 2) if intrinsic_pessimistic else None,
        "intrinsic_central": round(intrinsic_central, 2) if intrinsic_central else None,
        "intrinsic_optimistic": round(intrinsic_optimistic, 2) if intrinsic_optimistic else None,
        "confidence_width_pct": round(width_pct, 1) if width_pct else 0.0,
        "dcf_over_width_threshold": over_width,
        "dcf_zero_width_error": zero_width,
        "confidence": confidence,
        "current_price": current_price,
        "wacc": DEFAULT_WACC_RANGE["central"],
        "perpetual_growth_rate": DEFAULT_G_RANGE["central"],
        "note": "; ".join(note_parts) if note_parts else "三档DCF正常输出",
    }


# ── 辅助：DCF隐含回报率 ────────────────────────────────────────────────────

def compute_dcf_implied_return(
    intrinsic_central: float,
    current_price: float,
    years: int = 5,
) -> Optional[float]:
    """
    计算DCF隐含的年化回报率

    (intrinsic_central / current_price)^(1/years) - 1
    """
    if not intrinsic_central or not current_price or current_price <= 0:
        return None
    return (intrinsic_central / current_price) ** (1 / years) - 1


# 需要pandas
import pandas as pd
