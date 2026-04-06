"""
pe_pb_percentile.py: PE/PB历史分位计算（regime-aware）
=======================================================
协议要求：
  1. 历史分位必须打regime标签
  2. 默认使用 registration-system（2020+）后数据
  3. 双窗口输出：percentile_full（全量）和 percentile_recent（注册制后）
  4. 差异 > 20% → regime_discontinuity_warning: true
  5. PB是A股主估值锚，PE为辅

数据来源：akshare实时拉取 + 模块2历史HDF5数据
"""

from __future__ import annotations

import os
import sys
import signal
import warnings
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ── 路径配置 ──────────────────────────────────────────────────────────────
IMPL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 超时常量 ───────────────────────────────────────────────────────────────
AKSHARE_TIMEOUT = 60  # 秒

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("akshare fetch timed out")


# ── 申万行业列表 ──────────────────────────────────────────────────────────

SW1_INDUSTRIES = [
    "农林牧渔", "采掘", "化工", "钢铁", "有色金属",
    "电子", "汽车", "家用电器", "食品饮料", "纺织服装",
    "轻工制造", "医药生物", "公用事业", "交通运输", "房地产",
    "商业贸易", "休闲服务", "建筑材料", "建筑装饰", "电气设备",
    "机械设备", "国防军工", "计算机", "传媒", "通信",
    "银行", "非银金融",
]

# 已知股票行业映射（fallback）
STOCK_INDUSTRY_MAP = {
    "002014": "医药生物",   # 永新股份
    "600036": "银行",        # 招商银行
    "601318": "非银金融",   # 中国平安
    "600519": "食品饮料",   # 贵州茅台
    "000858": "食品饮料",   # 五粮液
    "600000": "银行",        # 浦发银行
    "000001": "银行",        # 平安银行
    "600518": "医药生物",   # 康美药业
    "000651": "家用电器",   # 格力电器
}


# ── PE/PB percentile 计算 ───────────────────────────────────────────────────

def _get_stock_pe_pb_history(
    stock_code: str,
    indicator: str = "PB",
    years: int = 10,
) -> pd.DataFrame:
    """
    获取个股PE/PB当前值（快照）
    PE/PB是市场指标，akshare提供当前快照，
    历史时间序列需要另外的API（这里用当前快照近似）
    """
    code_6d = stock_code.strip()[-6:]
    result = pd.DataFrame()  # 初始化，避免未定义引用

    try:
        import akshare as ak

        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(AKSHARE_TIMEOUT)
        try:
            if indicator == "PB":
                df_all = ak.stock_a_all_pb()
                if df_all is not None and not df_all.empty:
                    code_col = [c for c in df_all.columns if "代码" in c or "code" in c.lower()]
                    if code_col:
                        mask = df_all[code_col[0]].astype(str).str.zfill(6) == code_6d
                        df_row = df_all[mask]
                        if not df_row.empty:
                            pb_col = [c for c in df_all.columns if "市净率" in c or "PB" in c.upper()]
                            if pb_col:
                                pb_val = df_row.iloc[0][pb_col[0]]
                                if pd.notna(pb_val) and float(pb_val) > 0:
                                    result = pd.DataFrame({
                                        "date": [datetime.now()],
                                        "value": [float(pb_val)]
                                    })
            elif indicator == "PE":
                # PE全市场数据
                try:
                    df_pe = ak.stock_market_pe_lg()
                    if df_pe is not None and not df_pe.empty:
                        code_col = [c for c in df_pe.columns if "代码" in c or "code" in c.lower()]
                        if code_col:
                            mask = df_pe[code_col[0]].astype(str).str.zfill(6) == code_6d
                            df_row = df_pe[mask]
                            if not df_row.empty:
                                pe_col = [c for c in df_pe.columns if "市盈率" in c or "PE" in c.upper()]
                                if pe_col:
                                    pe_val = df_row.iloc[0][pe_col[0]]
                                    if pd.notna(pe_val):
                                        try:
                                            pe_f = float(pe_val)
                                            if 0 < pe_f < 10000:  # 合理PE范围
                                                result = pd.DataFrame({
                                                    "date": [datetime.now()],
                                                    "value": [pe_f]
                                                })
                                        except (ValueError, TypeError):
                                            pass
                except Exception:
                    pass
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

    except TimeoutError:
        logger.warning(f"PE/PB获取超时 [{stock_code}]")
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"PE/PB获取失败 [{stock_code}]: {e}")
        return pd.DataFrame()

    if result.empty:
        return pd.DataFrame()

    result = result.dropna(subset=["value", "date"])
    result["value"] = result["value"].replace([np.inf, -np.inf], np.nan)
    result = result.dropna(subset=["value"])
    return result[["date", "value"]]


def _get_industry_pe_pb_history(
    industry_name: str,
    indicator: str = "PB",
    years: int = 10,
) -> pd.DataFrame:
    """
    获取行业PE/PB历史时间序列
    使用akshare申万行业历史数据
    """
    try:
        import akshare as ak

        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(AKSHARE_TIMEOUT)
        try:
            # 申万行业历史PE/PB
            df = ak.sw_index_second_cons_sina(symbol="申万一级行业")  # fallback
        except Exception:
            pass

        # 尝试板块历史行情
        try:
            # 使用板块行情（东方财富）
            df = ak.stock_board_industry_hist_em(
                symbol=industry_name,
                period="yearly",
                start_date=f"{datetime.now().year - years}0101",
                end_date=datetime.now().strftime("%Y%m%d"),
            )
        except Exception:
            return pd.DataFrame()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

        if df is None or df.empty:
            return pd.DataFrame()

        # 尝试提取PB列
        result = pd.DataFrame()
        if indicator == "PB":
            for col in ["市净率", "PB", "pb", "PB_LF"]:
                if col in df.columns:
                    result["value"] = pd.to_numeric(df[col], errors="coerce")
                    break
        else:
            for col in ["市盈率", "PE", "pe", "PE_TTM"]:
                if col in df.columns:
                    result["value"] = pd.to_numeric(df[col], errors="coerce")
                    break

        if "value" not in result.columns:
            return pd.DataFrame()

        for col in ["日期", "date", "trade_date"]:
            if col in df.columns:
                result["date"] = pd.to_datetime(df[col], errors="coerce")
                break

        if "date" not in result.columns:
            return pd.DataFrame()

        result = result.dropna(subset=["value", "date"])
        result["value"] = result["value"].replace([np.inf, -np.inf], np.nan)
        result = result.dropna(subset=["value"])

        return result[["date", "value"]]

    except TimeoutError:
        logger.warning(f"行业PE/PB获取超时 [{industry_name}]")
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"行业PE/PB获取失败 [{industry_name}]: {e}")
        return pd.DataFrame()


def _compute_percentiles(
    values: List[float],
    actual: float,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    计算单值在一组值中的分位位置

    Returns
    -------
    (percentile_position, p20_threshold, p80_threshold)
        percentile_position: actual在分布中的分位（0-100）
        p20_threshold: 行业P20阈值
        p80_threshold: 行业P80阈值
    """
    if not values or len(values) < 3:
        return None, None, None

    arr = np.array(values)
    arr = arr[~np.isnan(arr)]

    if len(arr) < 3:
        return None, None, None

    p20 = float(np.nanpercentile(arr, 20))
    p50 = float(np.nanpercentile(arr, 50))
    p80 = float(np.nanpercentile(arr, 80))

    # 计算actual的分位
    if actual is None or np.isnan(actual):
        return None, p20, p80

    # 分位计算：在多少%的值以下
    pct = float(np.sum(arr <= actual) / len(arr) * 100)

    return pct, p20, p80


def _compute_regime_aware_percentile(
    stock_code: str,
    industry_name: str,
    indicator: str = "PB",
    current_value: Optional[float] = None,
) -> Dict[str, Any]:
    """
    计算regime-aware的历史分位

    1. 获取全量历史PE/PB（个股+行业）
    2. 过滤出注册制后数据
    3. 计算双窗口分位
    4. 判断断裂警告

    Returns
    -------
    Dict with keys:
        - percentile_full: 全量分位
        - percentile_recent: 注册制后分位（默认）
        - regime_discontinuity_warning: bool
        - threshold_p20, threshold_p80
        - confidence: high/medium/low
        - data_years: 有效数据年数
        - n_stocks_used: 行业成分股数量
        - note: str
    """
    # 获取个股历史数据
    df_stock = _get_stock_pe_pb_history(stock_code, indicator)

    # 获取行业历史数据（用于算阈值）
    df_industry = _get_industry_pe_pb_history(industry_name, indicator)

    # 合并，使用行业分布计算分位
    if df_industry.empty:
        # Fallback：使用个股自身历史分布
        if df_stock.empty:
            return {
                "percentile_full": None,
                "percentile_recent": None,
                "regime_discontinuity_warning": False,
                "threshold_p20": None,
                "threshold_p80": None,
                "confidence": "low",
                "data_years": 0,
                "n_stocks_used": 0,
                "note": "无历史数据",
            }

        df = df_stock.copy()
    else:
        df = df_industry.copy()

    # 日期处理
    df = df.sort_values("date")
    df["year"] = df["date"].dt.year

    # 打regime标签
    def regime_of_year(y: int) -> str:
        if y < 2005:
            return "pre-split-share"
        elif y < 2020:
            return "post-split-share"
        else:
            return "registration-system"

    df["regime"] = df["year"].apply(regime_of_year)

    # 全量分位
    full_values = df["value"].dropna().tolist()
    if not full_values:
        return {
            "percentile_full": None,
            "percentile_recent": None,
            "regime_discontinuity_warning": False,
            "threshold_p20": None,
            "threshold_p80": None,
            "confidence": "low",
            "data_years": 0,
            "n_stocks_used": 0,
            "note": "全量数据为空",
        }

    # 注册制后数据
    recent_df = df[df["year"] >= 2020]
    recent_values = recent_df["value"].dropna().tolist()

    # 当前值（从最新一期）
    if current_value is None:
        if not df.empty:
            current_value = float(df.sort_values("date").iloc[-1]["value"])

    # 计算分位
    pct_full, p20, p80 = _compute_percentiles(full_values, current_value)
    pct_recent, _, _ = _compute_percentiles(recent_values, current_value)

    # 检查断裂
    discontinuity = False
    if pct_full is not None and pct_recent is not None:
        if abs(pct_full - pct_recent) > 20.0:
            discontinuity = True

    # 置信度
    data_years = len(df["year"].unique())
    if data_years >= 10:
        confidence = "high"
    elif data_years >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "percentile_full": pct_full,
        "percentile_recent": pct_recent,
        "regime_discontinuity_warning": discontinuity,
        "threshold_p20": p20,
        "threshold_p80": p80,
        "confidence": confidence,
        "data_years": data_years,
        "n_stocks_used": len(df_industry) if not df_industry.empty else 1,
        "note": f"{industry_name} {indicator} {'⚠️断裂' if discontinuity else ''}",
    }


# ── 主入口函数 ─────────────────────────────────────────────────────────────

def get_pe_pb_percentile(
    stock_code: str,
    industry_name: str,
    indicator: str = "PB",
    current_value: Optional[float] = None,
) -> Dict[str, Any]:
    """
    获取PE/PB历史分位（regime-aware，双窗口）

    示例：
        result = get_pe_pb_percentile("002014", "医药生物", "PB")
        print(result["percentile_recent"], result["regime_discontinuity_warning"])

    Parameters
    ----------
    stock_code : str
        6位股票代码
    industry_name : str
        申万一级行业名称
    indicator : str
        "PB" 或 "PE"
    current_value : float, optional
        当前实际PE/PB值，若为None则从akshare实时获取

    Returns
    -------
    Dict（与PercentileResult字段对应）
    """
    return _compute_regime_aware_percentile(
        stock_code=stock_code,
        industry_name=industry_name,
        indicator=indicator,
        current_value=current_value,
    )


def get_current_pe_pb(stock_code: str) -> Tuple[Optional[float], Optional[float]]:
    """
    实时获取个股当前PE和PB
    Returns
    -------
    (pe, pb)
    """
    code_6d = stock_code.strip()[-6:]
    pe = None
    pb = None

    try:
        import akshare as ak

        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(AKSHARE_TIMEOUT)
        try:
            # PB: stock_a_all_pb (全市场PB快照)
            df_pb = ak.stock_a_all_pb()
            if df_pb is not None and not df_pb.empty:
                code_col = [c for c in df_pb.columns if "代码" in c][0]
                row = df_pb[df_pb[code_col].astype(str).str.zfill(6) == code_6d]
                if not row.empty:
                    pb_col = [c for c in df_pb.columns if "市净率" in c][0]
                    pb_val = row.iloc[0][pb_col]
                    if pd.notna(pb_val):
                        pb = float(pb_val)

            # PE: stock_market_pe_lg (全市场PE快照)
            df_pe = ak.stock_market_pe_lg()
            if df_pe is not None and not df_pe.empty:
                code_col = [c for c in df_pe.columns if "代码" in c][0]
                row = df_pe[df_pe[code_col].astype(str).str.zfill(6) == code_6d]
                if not row.empty:
                    pe_col = [c for c in df_pe.columns if "市盈率" in c][0]
                    pe_val = row.iloc[0][pe_col]
                    if pd.notna(pe_val):
                        try:
                            pe = float(pe_val)
                        except (ValueError, TypeError):
                            pass
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
    except Exception:
        pass

    return pe, pb
