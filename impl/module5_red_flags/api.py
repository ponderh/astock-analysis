"""
api.py: module5_red_flags 对外API
==================================
供外部系统调用的标准化接口
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional, Dict, Any, List

from .engine import RedFlagEngine, analyze as _analyze, REPORTS_DIR, STOCK_NAMES

logger = logging.getLogger(__name__)

# 全局引擎实例（可复用）
_global_engine: Optional[RedFlagEngine] = None


def get_engine(mda_enabled: bool = True) -> RedFlagEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = RedFlagEngine(mda_enabled=mda_enabled)
    return _global_engine


def set_stock_name(stock_code: str, stock_name: str) -> None:
    """手动设置股票名称映射"""
    code_6d = stock_code.strip()[-6:]
    STOCK_NAMES[code_6d] = stock_name


def screen(
    stock_code: str,
    stock_name: Optional[str] = None,
    mda_enabled: bool = True,
    save_report: bool = True,
    mda_year: int = 2024,
) -> Dict[str, Any]:
    """
    红旗筛查主入口
    ==============

    示例:
        result = screen("002014", "永新股份")
        print(result["verdict"], result["overall_score"])

    Parameters
    ----------
    stock_code : str
        股票代码（支持多种格式）
    stock_name : str, optional
        股票名称（会自动缓存）
    mda_enabled : bool
        是否启用MD&A（默认关闭，较慢）
    save_report : bool
        是否保存JSON报告（默认开启）
    mda_year : int
        MD&A分析年份

    Returns
    -------
    Dict (与ScoredReport.to_dict()一致)
    """
    if stock_name:
        set_stock_name(stock_code, stock_name)

    engine = get_engine(mda_enabled=mda_enabled)

    if save_report:
        report = engine.analyze_and_save(stock_code, mda_year=mda_year)
    else:
        report = engine.analyze(stock_code, mda_year=mda_year)

    return report.to_dict()


def screen_batch(
    stocks: List[tuple],
    mda_enabled: bool = True,
    save_reports: bool = True,
) -> List[Dict[str, Any]]:
    """
    批量红旗筛查

    Parameters
    ----------
    stocks : List[tuple]
        [(stock_code, stock_name), ...]

    Returns
    -------
    List[Dict] 每只股票的结果
    """
    results = []
    engine = get_engine(mda_enabled=mda_enabled)

    for code, name in stocks:
        set_stock_name(code, name)
        try:
            if save_reports:
                report = engine.analyze_and_save(code)
            else:
                report = engine.analyze(code)
            results.append(report.to_dict())
        except Exception as e:
            logger.error(f"红旗筛查失败 [{code}]: {e}")
            results.append({
                "stock_code": code.strip()[-6:],
                "stock_name": name,
                "report_date": date.today().isoformat(),
                "verdict": "异常",
                "error": str(e),
                "overall_score": 0,
                "red_flags": [],
                "yellow_flags": [],
                "extreme_flags": [],
            })

    return results


def load_report(stock_code: str, report_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    加载已保存的报告

    Parameters
    ----------
    stock_code : str
        股票代码
    report_date : str, optional
        报告日期（YYYY-MM-DD）。若为None，加载最新报告

    Returns
    -------
    Dict or None
    """
    code_6d = stock_code.strip()[-6:]
    if report_date is None:
        # 找最新的
        candidates = list(REPORTS_DIR.glob(f"{code_6d}_*.json"))
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        filepath = candidates[0]
    else:
        filename = f"{code_6d}_{report_date}.json"
        filepath = REPORTS_DIR / filename

    if not filepath.exists():
        return None

    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def list_reports(stock_code: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    列出已保存的报告

    Parameters
    ----------
    stock_code : str, optional
        过滤特定股票

    Returns
    -------
    List[Dict] 每条包含 stock_code, report_date, file_path, score, verdict
    """
    if stock_code:
        code_6d = stock_code.strip()[-6:]
        pattern = f"{code_6d}_*.json"
    else:
        pattern = "*.json"

    reports = []
    for fp in sorted(REPORTS_DIR.glob(pattern)):
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            reports.append({
                "stock_code": data.get("stock_code", ""),
                "stock_name": data.get("stock_name", ""),
                "report_date": data.get("report_date", ""),
                "verdict": data.get("verdict", ""),
                "overall_score": data.get("overall_score", 0),
                "file_path": str(fp),
            })
        except Exception as e:
            logger.warning(f"读取报告失败 {fp}: {e}")

    return reports


# 导出
__all__ = [
    "screen",
    "screen_batch",
    "load_report",
    "list_reports",
    "set_stock_name",
    "get_engine",
]
