"""
engine.py: 财务红旗引擎 — 核心串联逻辑
=====================================
整合模块2（历史财务）+ 模块9（治理筛查）+ 行业阈值库 + 模块6（MD&A）+ 模块7（公告）
对输入股票输出结构化红旗报告

调用流程:
    RedFlagEngine.analyze(stock_code) → ScoredReport → JSON报告
"""

from __future__ import annotations
import os
import json
import time
import logging
import warnings
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pathlib import Path

import numpy as np
import pandas as pd

# 抑制第三方库噪音
for _lib in ["urllib3", "requests", "PIL", "matplotlib"]:
    logging.getLogger(_lib).setLevel(logging.WARNING)
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

# ── 路径配置 ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

IMPL_DIR = BASE_DIR.parent.parent / "impl"

# ── 股票名称缓存 ─────────────────────────────────────────────────────────
STOCK_NAMES: Dict[str, str] = {
    "002014": "永新股份",
    "600518": "康美药业",
    "002450": "康得新",
    "300104": "乐视退",
    "600074": "保千里",
    "002604": "龙力生物",
}


def get_stock_name(stock_code: str) -> str:
    """获取股票名称，优先使用已知映射，否则返回代码"""
    code_6d = stock_code.strip()[-6:]
    return STOCK_NAMES.get(code_6d, code_6d)


# ── 导入各模块 ────────────────────────────────────────────────────────────

def _import_module2():
    """延迟导入module2（避免akshare超时阻塞）"""
    import sys
    sys.path.insert(0, str(IMPL_DIR))
    from module2_financial.api import get_financial_history, get_derived_metrics
    return get_financial_history, get_derived_metrics


def _import_module9():
    """延迟导入module9"""
    import sys
    sys.path.insert(0, str(IMPL_DIR))
    from module9_governance.screen import screen as governance_screen, GovernanceScreener
    return governance_screen, GovernanceScreener


def _import_audit_history():
    """延迟导入audit_history"""
    import sys
    sys.path.insert(0, str(IMPL_DIR))
    from module9_governance.audit_history import AuditHistoryFetcher
    return AuditHistoryFetcher


def _import_industry_thresholds():
    """延迟导入行业阈值"""
    import sys
    sys.path.insert(0, str(IMPL_DIR))
    from industry_thresholds.api import get_threshold, get_industry_class, get_red_flags as ind_get_red_flags
    return get_threshold, get_industry_class, ind_get_red_flags


def _import_module7():
    """延迟导入module7（直接导入fetcher绕过api.py的相对导入问题）"""
    import sys
    sys.path.insert(0, str(IMPL_DIR))
    from module7_announcements.fetcher import fetch_announcements
    from module7_announcements.parser import (
        NoticeType, ParsedNotice, parse_notices,
        classification_report, get_notices_by_type
    )
    # Re-implement the thin wrappers here to avoid relative import issues
    def get_latest_notices_local(stock_code, count=10, notice_types=None):
        try:
            raw = fetch_announcements(stock_code=stock_code, begin_time=None, end_time=None, max_notices=count*3)
            parsed = parse_notices(raw)
            if notice_types:
                type_enums = []
                for t in notice_types:
                    for et in NoticeType:
                        if et.value == t or t in et.value:
                            type_enums.append(et)
                if type_enums:
                    parsed = get_notices_by_type(parsed, type_enums)
            return [n.to_dict() for n in parsed[:count]]
        except Exception:
            return []

    return None, get_latest_notices_local, None


def _import_module6():
    """延迟导入module6（慢速，PDF下载）"""
    import sys
    sys.path.insert(0, str(IMPL_DIR))
    from module6_mda.pipeline import MDAPipeline
    from module6_mda.models import PipelineStage
    return MDAPipeline, PipelineStage


# ============================================================
# 数据获取函数
# ============================================================

def _fetch_governance(stock_code: str, stock_name: str, timeout: int = 45) -> Dict[str, Any]:
    """
    获取治理数据（来自module9）
    返回治理Block字典
    """
    try:
        governance_screen, _ = _import_module9()
        # 使用短超时
        import signal

        def handler(signum, frame):
            raise TimeoutError("governance timeout")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(timeout)

        try:
            report = governance_screen(stock_code, stock_name)
            signal.alarm(0)
        except TimeoutError:
            logger.warning(f"治理筛查超时 [{stock_code}]，使用降级数据")
            return _governance_fallback(stock_code, stock_name)
        except Exception as e:
            signal.alarm(0)
            logger.warning(f"治理筛查失败 [{stock_code}]: {e}")
            return _governance_fallback(stock_code, stock_name)

        sig = report.signals
        return {
            "pledge_ratio": sig.pledge_ratio_pct,
            "audit_score": _audit_opinion_to_score(sig.audit_opinions),
            "goodwill_pct": sig.goodwill_ratio_pct,
            "signal": sig.pledge_signal,
            "actual_controller": sig.actual_controller,
            "audit_opinions": sig.audit_opinions,
            "_raw_report": report.to_dict(),
            "is_delisted": getattr(report, 'is_delisted', False),
        }

    except Exception as e:
        logger.warning(f"治理数据获取异常 [{stock_code}]: {e}")
        return _governance_fallback(stock_code, stock_name)


def _governance_fallback(stock_code: str, stock_name: str) -> Dict[str, Any]:
    """治理数据降级返回值"""
    return {
        "pledge_ratio": 0.0,
        "audit_score": 0,
        "goodwill_pct": 0.0,
        "signal": "数据获取失败",
        "actual_controller": "",
        "audit_opinions": {},
        "_raw_report": None,
        "is_delisted": False,
    }


def _fetch_audit_history(stock_code: str, timeout: int = 20) -> Dict[str, Any]:
    """
    获取审计历史数据（来自module9_governance/audit_history.py）
    Bug 2 Fix: 退市股极旗判断需要读取历史审计记录
    """
    try:
        AuditHistoryFetcher = _import_audit_history()
        fetcher = AuditHistoryFetcher(timeout=timeout)
        opinions, signal = fetcher.get_audit_history(stock_code, years=8)
        # 检查是否有历史严重非标
        has_historical_non_standard = any(
            op in {"保留意见", "无法表示意见", "否定意见"}
            for op in opinions.values()
        )
        return {
            "opinions": opinions,
            "signal": signal,
            "has_historical_non_standard": has_historical_non_standard,
        }
    except Exception as e:
        logger.warning(f"审计历史获取失败 [{stock_code}]: {e}")
        return {
            "opinions": {},
            "signal": "需核实",
            "has_historical_non_standard": False,
        }


def _audit_opinion_to_score(opinions: Dict[str, str]) -> int:
    """审计意见字典转风险评分"""
    if not opinions:
        return 0
    abnormal = {"保留意见", "无法表示意见", "否定意见", "带强调事项段的无保留意见"}
    has_abnormal = any(op in abnormal for op in opinions.values())
    return 2 if has_abnormal else 0


def _fetch_financial(stock_code: str, years: int = 10) -> Dict[str, Any]:
    """
    获取财务数据（来自module2，HDF5加速）
    返回财务Block字典
    """
    try:
        get_financial_history, get_derived_metrics = _import_module2()

        # 使用HDF5数据（更快）
        # 注意：会先用akshare尝试，超时后降级到HDF5
        # 这里我们直接用get_financial_history让它自己处理超时

        import signal

        def handler(signum, frame):
            raise TimeoutError("financial fetch timeout")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(40)

        try:
            df = get_financial_history(stock_code, years=years, include_derived=False)
            signal.alarm(0)
        except TimeoutError:
            logger.warning(f"财务数据获取超时 [{stock_code}]，使用HDF5")
            signal.alarm(0)
            df = pd.DataFrame()
        except Exception as e:
            signal.alarm(0)
            logger.warning(f"财务数据计算异常 [{stock_code}]: {e}，使用原始数据")
            try:
                df = get_financial_history(stock_code, years=years, include_derived=False)
            except Exception:
                df = pd.DataFrame()
        except Exception as e:
            signal.alarm(0)
            logger.warning(f"财务数据获取失败 [{stock_code}]: {e}")
            df = pd.DataFrame()

        # 计算衍生指标
        result: Dict[str, Any] = {
            "df": df,
            "roe_latest": None,
            "net_profit_cash_ratio": None,
            "revenue_growth_yoy": None,
            "inventory_turnover_trend": None,
            "consecutive_loss_years": 0,
            "latest_year": "",
        }

        if df.empty:
            return result

        # 提取最新一期关键指标
        latest_row = df.sort_values("statDate").tail(1).iloc[0]

        # ROE
        for col in ["roe", "ROE", "净资产收益率"]:
            if col in latest_row.index and pd.notna(latest_row[col]):
                result["roe_latest"] = float(latest_row[col])
                break

        # 净现比
        for col in ["net_cash_ratio", "净现比", "cfo_to_net_profit_ratio"]:
            if col in latest_row.index and pd.notna(latest_row[col]):
                result["net_profit_cash_ratio"] = float(latest_row[col])
                break

        # 收入增长率
        if "revenue_growth" in df.columns:
            valid = df.dropna(subset=["revenue_growth"])
            if not valid.empty:
                result["revenue_growth_yoy"] = float(valid.sort_values("statDate").iloc[-1]["revenue_growth"])

        # 连续亏损
        from .scorer import compute_consecutive_losses
        loss_years, latest_yr = compute_consecutive_losses(df)
        result["consecutive_loss_years"] = loss_years
        result["latest_year"] = latest_yr

        # 存货周转趋势
        from .scorer import compute_inventory_trend
        inv_trend = compute_inventory_trend(df)
        result["inventory_turnover_trend"] = inv_trend

        return result

    except Exception as e:
        logger.warning(f"财务数据处理异常 [{stock_code}]: {e}")
        return {
            "df": pd.DataFrame(),
            "roe_latest": None,
            "net_profit_cash_ratio": None,
            "revenue_growth_yoy": None,
            "inventory_turnover_trend": None,
            "consecutive_loss_years": 0,
            "latest_year": "",
        }


def _fetch_industry_thresholds(stock_code: str) -> Dict[str, Any]:
    """
    获取行业阈值数据（来自industry_thresholds模块）
    """
    try:
        get_threshold, get_industry_class, _ = _import_industry_thresholds()

        industry = get_industry_class(stock_code)
        result: Dict[str, Any] = {
            "industry_name": industry,
            "roe_p10": None,
            "net_profit_cash_p10": None,
            "revenue_growth_p10": None,
            "flags_triggered": [],
        }

        for indicator, key in [("ROE", "roe_p10"), ("CFO_TO_REVENUE", "net_profit_cash_p10")]:
            try:
                th = get_threshold(industry, indicator, percentile=10)
                result[key] = th.get("value") or th.get("p10")
            except Exception:
                pass

        return result

    except Exception as e:
        logger.warning(f"行业阈值获取失败 [{stock_code}]: {e}")
        return {
            "industry_name": "",
            "roe_p10": None,
            "net_profit_cash_p10": None,
            "revenue_growth_p10": None,
            "flags_triggered": [],
        }


def _fetch_mda(stock_code: str, year: int = 2024, timeout: int = 120) -> Dict[str, Any]:
    """
    获取MD&A分析数据（来自module6）
    注意：这是最慢的步骤，需要下载PDF
    降级策略：超时则返回空结果
    """
    try:
        MDAPipeline, _ = _import_module6()

        # 标准化代码
        if stock_code.startswith("SZ") or stock_code.startswith("SH"):
            code = stock_code[2:]
        else:
            code = stock_code[-6:]

        org_id_map = {
            "002014": "gssz0002014",
            "600518": "gssz0600518",
        }
        org_id = org_id_map.get(code, f"gssz{code}")

        pipeline = MDAPipeline(stock_code=code, org_id=org_id)

        import signal

        def handler(signum, frame):
            raise TimeoutError("MDA timeout")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(timeout)

        try:
            mda_result = pipeline.process_one_year(year)
            signal.alarm(0)
        except TimeoutError:
            logger.warning(f"MD&A分析超时 [{stock_code}]，跳过MDA")
            signal.alarm(0)
            return _mda_fallback()
        except Exception as e:
            signal.alarm(0)
            logger.warning(f"MD&A分析失败 [{stock_code}]: {e}")
            return _mda_fallback()

        # 解析结构化数据
        if mda_result.strategic_analysis and mda_result.strategic_analysis.structured_data:
            sd = mda_result.strategic_analysis.structured_data
            themes = sd.get("key_strategic_themes", [])
            if isinstance(themes, list) and themes:
                if isinstance(themes[0], dict):
                    theme_labels = [t.get("description", t.get("theme", "")) for t in themes[:5]]
                else:
                    theme_labels = themes[:5]
            else:
                theme_labels = []

            risks = sd.get("risk_factors", [])
            if isinstance(risks, list) and risks:
                if isinstance(risks[0], dict):
                    risk_labels = [r.get("risk", r.get("description", "")) for r in risks[:5]]
                else:
                    risk_labels = risks[:5]
            else:
                risk_labels = []

            confidence = mda_result.quality_score.overall_score if mda_result.quality_score else 0.0

            return {
                "strategy_confidence": confidence / 100.0,
                "key_themes": theme_labels,
                "risk_factors": risk_labels,
                "raw_data": sd,
                "_pipeline_result": mda_result,
            }
        else:
            return _mda_fallback()

    except Exception as e:
        logger.warning(f"MD&A数据获取异常 [{stock_code}]: {e}")
        return _mda_fallback()


def _mda_fallback() -> Dict[str, Any]:
    """MDA数据降级返回值"""
    return {
        "strategy_confidence": 0.0,
        "key_themes": [],
        "risk_factors": [],
        "raw_data": {},
    }


def _fetch_announcements(stock_code: str, max_count: int = 100) -> Dict[str, Any]:
    """
    获取公告数据（来自module7）
    """
    try:
        get_announcements, get_latest_notices, get_yjyg_notices = _import_module7()

        code_6d = stock_code.strip()[-6:]

        import signal

        def handler(signum, frame):
            raise TimeoutError("announcements timeout")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(30)

        try:
            # 获取最新公告
            notices = get_latest_notices(code_6d, count=max_count)
            signal.alarm(0)
        except TimeoutError:
            logger.warning(f"公告获取超时 [{stock_code}]")
            signal.alarm(0)
            notices = []
        except Exception as e:
            signal.alarm(0)
            logger.warning(f"公告获取失败 [{stock_code}]: {e}")
            notices = []

        # 解析业绩预告
        earnings_warnings: List[Dict[str, Any]] = []
        corrective_notices: List[Dict[str, Any]] = []

        for n in notices:
            title = n.get("title", "")
            notice_date = n.get("notice_date", "")
            ntype = n.get("type_label", "")

            if "业绩预告" in title or "业绩更正" in title or "业绩修正" in title:
                earnings_warnings.append({
                    "title": title,
                    "notice_date": notice_date[:10] if notice_date else "",
                    "type": ntype,
                    "extracted_amount": n.get("extracted_amount"),
                    "extracted_change_pct": n.get("extracted_change_pct"),
                })

            if "更正" in title or "补充" in title or "修订" in title:
                corrective_notices.append({
                    "title": title,
                    "notice_date": notice_date[:10] if notice_date else "",
                    "type": ntype,
                })

        return {
            "recent_count": len(notices),
            "earnings_warnings": earnings_warnings[:10],
            "corrective_notices": corrective_notices[:10],
        }

    except Exception as e:
        logger.warning(f"公告数据获取异常 [{stock_code}]: {e}")
        return {
            "recent_count": 0,
            "earnings_warnings": [],
            "corrective_notices": [],
        }


# ============================================================
# RedFlagEngine
# ============================================================

class RedFlagEngine:
    """
    财务红旗分析引擎
    =================

    示例:
        engine = RedFlagEngine()
        report = engine.analyze("002014")
        print(report.summary())
    """

    def __init__(self, mda_enabled: bool = False, timeout_per_source: int = 60):
        """
        Parameters
        ----------
        mda_enabled : bool
            是否启用MD&A分析（默认关闭，因其需要下载PDF较慢）
        timeout_per_source : int
            各数据源超时秒数
        """
        self.mda_enabled = mda_enabled
        self.timeout_per_source = timeout_per_source

    def analyze(self, stock_code: str, mda_year: int = 2024) -> "ScoredReport":
        """
        对单只股票进行完整的红旗分析

        Parameters
        ----------
        stock_code : str
            股票代码（支持 002014 / SZ002014 / SH600000 格式）
        mda_year : int
            MD&A分析的年份（默认2024）

        Returns
        -------
        ScoredReport
        """
        start_time = time.time()
        code_6d = stock_code.strip()[-6:]
        stock_name = get_stock_name(code_6d)
        report_date = date.today().isoformat()

        logger.info(f"[{code_6d}] 开始红旗分析 | 股票名称: {stock_name}")

        # ── Step 1: 并行获取各模块数据 ────────────────────────────────────
        t0 = time.time()

        # 1a. 治理筛查
        gov_data = _fetch_governance(code_6d, stock_name, timeout=min(45, self.timeout_per_source))

        # Bug 2 Fix: 退市股需要读取历史审计记录触发极旗
        audit_hist_data = _fetch_audit_history(code_6d, timeout=min(20, self.timeout_per_source))

        # 1b. 财务数据
        fin_data = _fetch_financial(code_6d, years=10)

        # 1c. 行业阈值
        ind_data = _fetch_industry_thresholds(code_6d)

        # 1d. 公告数据
        ann_data = _fetch_announcements(code_6d, max_count=50)

        fetch_time = time.time() - t0
        logger.info(f"[{code_6d}] 数据获取完成，耗时: {fetch_time:.1f}s")

        # 1e. MD&A（可选）
        mda_data: Dict[str, Any] = _mda_fallback()
        if self.mda_enabled:
            t_mda = time.time()
            mda_data = _fetch_mda(code_6d, year=mda_year, timeout=120)
            logger.info(f"[{code_6d}] MD&A完成，耗时: {time.time()-t_mda:.1f}s")

        # ── Step 2: 构建各Block ─────────────────────────────────────────────

        # GovernanceBlock
        from .scorer import GovernanceBlock
        gov_block = GovernanceBlock(
            pledge_ratio=gov_data.get("pledge_ratio", 0.0),
            audit_score=gov_data.get("audit_score", 0),
            goodwill_pct=gov_data.get("goodwill_pct", 0.0),
            signal=gov_data.get("signal", "未知"),
            actual_controller=gov_data.get("actual_controller", ""),
            audit_opinions=gov_data.get("audit_opinions", {}),
            is_delisted=gov_data.get("is_delisted", False),
        )

        # FinancialBlock
        from .scorer import FinancialBlock
        fin_block = FinancialBlock(
            roe_latest=fin_data.get("roe_latest"),
            net_profit_cash_ratio=fin_data.get("net_profit_cash_ratio"),
            revenue_growth_yoy=fin_data.get("revenue_growth_yoy"),
            inventory_turnover_trend=fin_data.get("inventory_turnover_trend"),
            consecutive_loss_years=fin_data.get("consecutive_loss_years", 0),
            latest_year=fin_data.get("latest_year", ""),
        )

        # IndustryThresholdBlock
        from .scorer import IndustryThresholdBlock
        ind_block = IndustryThresholdBlock(
            industry_name=ind_data.get("industry_name", ""),
            roe_p10=ind_data.get("roe_p10"),
            net_profit_cash_p10=ind_data.get("net_profit_cash_p10"),
            revenue_growth_p10=ind_data.get("revenue_growth_p10"),
            flags_triggered=ind_data.get("flags_triggered", []),
        )

        # MDABlock
        from .scorer import MDABlock
        mda_block = MDABlock(
            strategy_confidence=mda_data.get("strategy_confidence", 0.0),
            key_themes=mda_data.get("key_themes", []),
            risk_factors=mda_data.get("risk_factors", []),
            raw_data=mda_data.get("raw_data", {}),
        )

        # AnnouncementBlock
        from .scorer import AnnouncementBlock
        ann_block = AnnouncementBlock(
            recent_count=ann_data.get("recent_count", 0),
            earnings_warnings=ann_data.get("earnings_warnings", []),
            corrective_notices=ann_data.get("corrective_notices", []),
        )

        # ── Step 3: 评分 ────────────────────────────────────────────────────
        from .scorer import RedFlagScorer
        scorer = RedFlagScorer()
        scored = scorer.score(
            stock_code=code_6d,
            stock_name=stock_name,
            governance_block=gov_block,
            financial_block=fin_block,
            threshold_block=ind_block,
            mda_block=mda_block,
            announcement_block=ann_block,
            report_date=report_date,
            audit_history=audit_hist_data,
        )

        total_time = time.time() - start_time
        logger.info(f"[{code_6d}] 红旗分析完成 | verdict={scored.verdict} | "
                    f"score={scored.overall_score} | 耗时: {total_time:.1f}s | "
                    f"红旗: {len(scored.red_flags)}红/{len(scored.yellow_flags)}黄/{len(scored.extreme_flags)}极")

        return scored

    def analyze_and_save(self, stock_code: str, mda_year: int = 2024) -> "ScoredReport":
        """
        分析并保存报告到JSON文件
        返回 ScoredReport
        """
        report = self.analyze(stock_code, mda_year=mda_year)

        # 保存JSON
        filename = f"{stock_code.strip()[-6:]}_{date.today().isoformat()}.json"
        filepath = REPORTS_DIR / filename

        report_dict = report.to_dict()
        # 清理不可JSON序列化的字段
        report_dict_clean = _sanitize_for_json(report_dict)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_dict_clean, f, ensure_ascii=False, indent=2)

        logger.info(f"报告已保存: {filepath}")
        return report


def _sanitize_for_json(obj):
    """清理不可JSON序列化的对象"""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        return str(obj)


# ============================================================
# 快速入口函数
# ============================================================

def analyze(stock_code: str, stock_name: Optional[str] = None,
            mda_enabled: bool = True, save: bool = False) -> "ScoredReport":
    """
    一行代码红旗分析

    示例:
        report = analyze("002014")
        print(report.summary())
    """
    # 更新全局名称映射
    if stock_name:
        code_6d = stock_code.strip()[-6:]
        STOCK_NAMES[code_6d] = stock_name

    engine = RedFlagEngine(mda_enabled=mda_enabled)
    if save:
        return engine.analyze_and_save(stock_code)
    else:
        return engine.analyze(stock_code)


__all__ = [
    "RedFlagEngine",
    "RedFlagScorer",
    "analyze",
    "STOCK_NAMES",
]
