"""
api.py: module5_valuation 对外API
==================================
供外部系统调用的标准化估值分析接口

示例:
    from module5_valuation.api import analyze, get_valuation
    result = analyze("002014")
    print(result["composite_signal"]["overall_verdict"])
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional, Dict, Any, List

from .engine import ValuationEngine, analyze as _analyze, REPORTS_DIR, STOCK_NAMES

logger = logging.getLogger(__name__)

_global_engine: Optional[ValuationEngine] = None


def get_engine() -> ValuationEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = ValuationEngine()
    return _global_engine


def set_stock_name(stock_code: str, stock_name: str) -> None:
    """手动设置股票名称映射"""
    code_6d = stock_code.strip()[-6:]
    STOCK_NAMES[code_6d] = stock_name


def analyze(
    stock_code: str,
    stock_name: Optional[str] = None,
    save_report: bool = True,
) -> Dict[str, Any]:
    """
    估值分析主入口

    示例:
        result = analyze("002014", "永新股份")
        print(result["composite_signal"]["overall_verdict"])

    Parameters
    ----------
    stock_code : str
        股票代码
    stock_name : str, optional
        股票名称
    save_report : bool
        是否保存JSON报告

    Returns
    -------
    Dict matching ValuationBlock.to_dict()
    """
    if stock_name:
        set_stock_name(stock_code, stock_name)

    engine = get_engine()

    if save_report:
        return engine.analyze_and_save(stock_code)
    else:
        return engine.analyze(stock_code)


def analyze_with_graham_included(
    stock_code: str,
    stock_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    估值分析（含格雷厄姆数纳入综合信号）
    仅当用户明确要求时使用（graham_included=True）
    """
    result = analyze(stock_code, stock_name, save_report=False)

    # 格雷厄姆数纳入综合信号（显式开启）
    graham = result.get("graham_result", {})
    if graham and graham.get("graham_number"):
        cs = result["composite_signal"]
        cs["graham_included"] = True
        cs["method_weights"]["graham"] = 0.15  # 格雷厄姆权重15%
        # 重新计算综合分（简化）
        g_verdict = graham.get("verdict", "")
        g_score = 50.0
        if "安全" in g_verdict:
            g_score = 75.0
        elif "高估" in g_verdict:
            g_score = 25.0

        w = cs["method_weights"]
        total_w = w["pe_pb_percentile"] + w["dcf"] + w["bank_pb"] + w["graham"]
        if total_w > 0:
            cs["overall_score"] = round(
                (result["composite_signal"].get("pe_pb_score", 50) * w["pe_pb_percentile"]
                 + result["composite_signal"].get("dcf_score", 50) * w["dcf"]
                 + result["composite_signal"].get("bank_pb_score", 50) * w["bank_pb"]
                 + g_score * w["graham"]) / total_w, 1
            )

    return result


def batch_analyze(
    stocks: List[tuple],
) -> List[Dict[str, Any]]:
    """
    批量估值分析

    Parameters
    ----------
    stocks : List[tuple]
        [(stock_code, stock_name), ...]

    Returns
    -------
    List[Dict] 每只股票的结果
    """
    results = []
    for code, name in stocks:
        set_stock_name(code, name)
        try:
            result = analyze(code, save_report=False)
            results.append(result)
        except Exception as e:
            logger.error(f"估值分析失败 [{code}]: {e}")
            results.append({
                "stock_code": code.strip()[-6:],
                "stock_name": name,
                "report_date": date.today().isoformat(),
                "composite_signal": {"overall_verdict": "异常", "overall_score": 0.0},
                "error": str(e),
            })
    return results


def load_valuation_report(
    stock_code: str,
    report_date: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """加载已保存的估值报告"""
    code_6d = stock_code.strip()[-6:]

    if report_date is None:
        candidates = list(Path(REPORTS_DIR).glob(f"{code_6d}_valuation_*.json"))
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        filepath = candidates[0]
    else:
        filename = f"{code_6d}_valuation_{report_date}.json"
        filepath = Path(REPORTS_DIR) / filename

    if not filepath.exists():
        return None

    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def list_valuation_reports(
    stock_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """列出已保存的估值报告"""
    if stock_code:
        pattern = f"{stock_code.strip()[-6:]}_valuation_*.json"
    else:
        pattern = "*_valuation_*.json"

    reports = []
    for fp in sorted(Path(REPORTS_DIR).glob(pattern)):
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            cs = data.get("composite_signal", {})
            reports.append({
                "stock_code": data.get("stock_code", ""),
                "stock_name": data.get("stock_name", ""),
                "report_date": data.get("report_date", ""),
                "verdict": cs.get("overall_verdict", ""),
                "score": cs.get("overall_score", 0),
                "file_path": str(fp),
            })
        except Exception as e:
            logger.warning(f"读取报告失败 {fp}: {e}")

    return reports


__all__ = [
    "analyze",
    "analyze_with_graham_included",
    "batch_analyze",
    "load_valuation_report",
    "list_valuation_reports",
    "set_stock_name",
    "get_engine",
]
