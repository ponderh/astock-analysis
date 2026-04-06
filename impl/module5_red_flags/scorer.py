"""
scorer.py: 财务红旗评分引擎
==========================
综合治理信号、财务指标、行业阈值，判断红旗严重程度并输出评分

评分体系:
  - 基础分: 100
  - 极端风险（清零项）: verdict="高风险", 红旗+3
  - 高风险红旗: -15分/项
  - 中风险黄旗: -8分/项
  - 行业阈值比较: 单独标记
  - overall_score: 0-100
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
import pandas as pd


# ============================================================
# 股票名称映射（补充akshare查询不到的）
# ============================================================
STOCK_NAME_MAP = {
    "002014": "永新股份",
    "600518": "康美药业",
    "002450": "康得新",
    "300104": "乐视",
    "600000": "浦发银行",
    "600036": "招商银行",
    "000001": "平安银行",
    "601318": "中国平安",
    "000858": "五粮液",
    "600519": "贵州茅台",
}


@dataclass
class RedFlag:
    """单条红旗"""
    code: str           # 红旗代码
    label: str          # 中文描述
    severity: str       # RED | YELLOW | EXTREME
    source_module: str  # 来源模块
    detail: str         # 详细说明
    numeric_value: Optional[float] = None
    threshold: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GovernanceBlock:
    """治理信号块"""
    pledge_ratio: float = 0.0
    audit_score: int = 0      # 0=clean, 1=存疑, 2=非标
    goodwill_pct: float = 0.0
    signal: str = "未知"
    actual_controller: str = ""
    audit_opinions: Dict[str, str] = field(default_factory=dict)
    is_delisted: bool = False  # Bug 2 Fix: 退市股标识

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FinancialBlock:
    """财务指标块"""
    roe_latest: Optional[float] = None
    net_profit_cash_ratio: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    net_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    inventory_turnover_trend: Optional[float] = None  # 趋势（正值=改善，负值=恶化）
    consecutive_loss_years: int = 0   # 连续亏损年数
    latest_year: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IndustryThresholdBlock:
    """行业阈值块"""
    industry_name: str = ""
    roe_p10: Optional[float] = None
    net_profit_cash_p10: Optional[float] = None
    revenue_growth_p10: Optional[float] = None
    flags_triggered: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MDABlock:
    """MD&A分析块"""
    strategy_confidence: float = 0.0
    key_themes: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    raw_data: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnnouncementBlock:
    """公告块"""
    recent_count: int = 0
    earnings_warnings: List[Dict] = field(default_factory=list)
    corrective_notices: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScoredReport:
    """评分后的完整报告"""
    stock_code: str
    stock_name: str
    report_date: str
    verdict: str                          # 通过 / 存疑 / 高风险
    governance: GovernanceBlock
    financial: FinancialBlock
    industry_thresholds: IndustryThresholdBlock
    mda: MDABlock
    announcements: AnnouncementBlock
    overall_score: int                   # 0-100
    red_flags: List[RedFlag]             # 所有红旗列表
    yellow_flags: List[RedFlag]          # 黄旗列表
    extreme_flags: List[RedFlag]         # 极端红旗列表
    scoring_details: Dict[str, Any]      # 评分详情
    verdict_reason: str = ""              # verdict判断原因
    data_source: str = "full"            # 数据来源标记: full/partial/degraded

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "report_date": self.report_date,
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
            "governance": self.governance.to_dict(),
            "financial": self.financial.to_dict(),
            "industry_thresholds": self.industry_thresholds.to_dict(),
            "mda": self.mda.to_dict(),
            "announcements": self.announcements.to_dict(),
            "overall_score": self.overall_score,
            "red_flags": [f.to_dict() for f in self.red_flags],
            "yellow_flags": [f.to_dict() for f in self.yellow_flags],
            "extreme_flags": [f.to_dict() for f in self.extreme_flags],
            "scoring_details": self.scoring_details,
            "data_source": self.data_source,
        }

    def summary(self) -> str:
        """人类可读摘要"""
        score = self.overall_score
        verdict_icon = {"通过": "🟢", "存疑": "🟡", "高风险": "🔴"}.get(self.verdict, "⚪")
        flags = self.red_flags + self.yellow_flags
        flag_str = f"{len(self.red_flags)}红/{len(self.yellow_flags)}黄" if flags else "无"
        lines = [
            f"{verdict_icon} {self.stock_code} {self.stock_name} — 红旗报告",
            f"  评分: {score}/100 | 结论: {self.verdict}",
            f"  红旗: {flag_str}",
        ]
        if self.red_flags:
            lines.append("  🔴 红旗:")
            for f in self.red_flags:
                lines.append(f"    • {f.code}: {f.label} ({f.detail})")
        if self.yellow_flags:
            lines.append("  🟡 黄旗:")
            for f in self.yellow_flags:
                lines.append(f"    • {f.code}: {f.label} ({f.detail})")
        return "\n".join(lines)


class RedFlagScorer:
    """
    红旗评分器
    ==========
    接收各模块数据，输出评分+红旗列表
    """

    # 扣分规则
    DEDUCTIONS = {
        # 极端风险（立即清零级）
        "audit_non_standard_recent": -30,    # 近3年审计非标
        "consecutive_loss_2yr": -30,          # 连续2年亏损
        "extreme_pledge": -30,                # 质押>50%
        "extreme_goodwill": -30,              # 商誉>50%

        # 高风险红旗（-15分/项）
        "high_pledge": -15,                   # 质押30-50%
        "high_goodwill": -15,                 # 商誉30-50%
        "low_net_cash_ratio": -15,           # 净现比<0.3
        "low_roe_vs_industry": -15,           # ROE<行业P10
        "inventory_turnover_worsening": -15,  # 存货周转持续恶化
        "revenue_decline": -15,               # 收入持续下滑

        # 中风险黄旗（-8分/项）
        "medium_pledge": -8,                  # 质押20-30%
        "medium_net_cash_ratio": -8,          # 净现比0.3-0.5
        "audit_history_non_standard": -8,    # 历史审计非标（已过追诉期）
        "medium_goodwill": -8,                # 商誉10-30%
        "revenue_growth_slowdown": -8,        # 收入增速放缓
    }

    def __init__(self):
        pass

    def score(
        self,
        stock_code: str,
        stock_name: str,
        governance_block: GovernanceBlock,
        financial_block: FinancialBlock,
        threshold_block: IndustryThresholdBlock,
        mda_block: MDABlock,
        announcement_block: AnnouncementBlock,
        report_date: str,
        audit_history: Optional[Dict[str, Any]] = None,
    ) -> ScoredReport:
        """
        核心评分方法

        Parameters
        ----------
        audit_history : dict, optional
            来自 AuditHistoryFetcher.get_audit_history() 的历史审计记录。
            键包含: 'opinions' (Dict[str,str]), 'signal' (str),
            'has_historical_non_standard' (bool)
        """
        base_score = 100
        red_flags: List[RedFlag] = []
        yellow_flags: List[RedFlag] = []
        extreme_flags: List[RedFlag] = []
        deductions: Dict[str, float] = {}

        # ── 1. 极端风险检查 ──────────────────────────────────────────────

        # 1a. 审计意见非标（近3年，当前数据）
        recent_opinions = {
            y: op for y, op in governance_block.audit_opinions.items()
            if op in {"保留意见", "无法表示意见", "否定意见", "带强调事项段的无保留意见"}
        }
        if recent_opinions:
            flag = RedFlag(
                code="AUDIT_NON_STANDARD",
                label="审计意见非标（近3年）",
                severity="EXTREME",
                source_module="module9_governance",
                detail=f"涉及年份: {list(recent_opinions.keys())}, 意见: {list(recent_opinions.values())}",
            )
            extreme_flags.append(flag)
            deductions["audit_non_standard_recent"] = self.DEDUCTIONS["audit_non_standard_recent"]

        # 1e. 退市股：从历史审计记录判断极端风险（Bug 2 Fix）
        # 当当前 audit_opinions 为空（退市股无法获取当前数据）
        # 但历史审计记录存在非标意见时，也触发极旗
        is_delisted = governance_block.audit_score == 0 and not recent_opinions
        if is_delisted and audit_history:
            has_historical_non_standard = audit_history.get("has_historical_non_standard", False)
            if has_historical_non_standard:
                severe_hist = {
                    y: op for y, op in audit_history.get("opinions", {}).items()
                    if op in {"保留意见", "无法表示意见", "否定意见"}
                }
                flag = RedFlag(
                    code="AUDIT_HISTORICAL_NON_STANDARD",
                    label="审计历史存在严重非标意见（退市股）",
                    severity="EXTREME",
                    source_module="module9_governance",
                    detail=f"历史严重非标: {severe_hist}",
                )
                extreme_flags.append(flag)
                deductions["audit_non_standard_recent"] = self.DEDUCTIONS["audit_non_standard_recent"]

        # 1b. 连续2年亏损
        if financial_block.consecutive_loss_years >= 2:
            flag = RedFlag(
                code="CONSECUTIVE_LOSS_2YR",
                label="净利润连续2年亏损",
                severity="EXTREME",
                source_module="module2_financial",
                detail=f"连续亏损{financial_block.consecutive_loss_years}年（最新:{financial_block.latest_year}）",
            )
            extreme_flags.append(flag)
            deductions["consecutive_loss_2yr"] = self.DEDUCTIONS["consecutive_loss_2yr"]

        # 1c. 质押比例>50%（极端）
        if governance_block.pledge_ratio > 50.0:
            flag = RedFlag(
                code="EXTREME_PLEDGE",
                label="股权质押比例过高（>50%）",
                severity="EXTREME",
                source_module="module9_governance",
                detail=f"实控人质押比例: {governance_block.pledge_ratio:.1f}%",
                numeric_value=governance_block.pledge_ratio,
                threshold=50.0,
            )
            extreme_flags.append(flag)
            deductions["extreme_pledge"] = self.DEDUCTIONS["extreme_pledge"]

        # 1d. 商誉占比>50%（极端）
        if governance_block.goodwill_pct > 50.0:
            flag = RedFlag(
                code="EXTREME_GOODWILL",
                label="商誉占比极高（>50%）",
                severity="EXTREME",
                source_module="module9_governance",
                detail=f"商誉/净资产: {governance_block.goodwill_pct:.1f}%",
                numeric_value=governance_block.goodwill_pct,
                threshold=50.0,
            )
            extreme_flags.append(flag)
            deductions["extreme_goodwill"] = self.DEDUCTIONS["extreme_goodwill"]

        # ── 2. 高风险红旗检查 ───────────────────────────────────────────

        # 2a. 质押比例 30-50%（高风险）
        if 30.0 < governance_block.pledge_ratio <= 50.0:
            flag = RedFlag(
                code="HIGH_PLEDGE",
                label="股权质押比例偏高（30-50%）",
                severity="RED",
                source_module="module9_governance",
                detail=f"实控人质押比例: {governance_block.pledge_ratio:.1f}%",
                numeric_value=governance_block.pledge_ratio,
                threshold=30.0,
            )
            red_flags.append(flag)
            deductions["high_pledge"] = self.DEDUCTIONS["high_pledge"]

        # 2b. 质押比例 20-30%（中风险）
        elif 20.0 < governance_block.pledge_ratio <= 30.0:
            flag = RedFlag(
                code="MEDIUM_PLEDGE",
                label="股权质押比例偏高（20-30%）",
                severity="YELLOW",
                source_module="module9_governance",
                detail=f"实控人质押比例: {governance_block.pledge_ratio:.1f}%",
                numeric_value=governance_block.pledge_ratio,
                threshold=20.0,
            )
            yellow_flags.append(flag)
            deductions["medium_pledge"] = self.DEDUCTIONS["medium_pledge"]

        # 2c. 商誉占比 30-50%（高风险）
        if 30.0 < governance_block.goodwill_pct <= 50.0:
            flag = RedFlag(
                code="HIGH_GOODWILL",
                label="商誉占比偏高（30-50%）",
                severity="RED",
                source_module="module9_governance",
                detail=f"商誉/净资产: {governance_block.goodwill_pct:.1f}%",
                numeric_value=governance_block.goodwill_pct,
                threshold=30.0,
            )
            red_flags.append(flag)
            deductions["high_goodwill"] = self.DEDUCTIONS["high_goodwill"]

        # 2d. 商誉占比 10-30%（中风险）
        elif 10.0 < governance_block.goodwill_pct <= 30.0:
            flag = RedFlag(
                code="MEDIUM_GOODWILL",
                label="商誉占比中等（10-30%）",
                severity="YELLOW",
                source_module="module9_governance",
                detail=f"商誉/净资产: {governance_block.goodwill_pct:.1f}%",
                numeric_value=governance_block.goodwill_pct,
                threshold=10.0,
            )
            yellow_flags.append(flag)
            deductions["medium_goodwill"] = self.DEDUCTIONS["medium_goodwill"]

        # 2e. 净现比<0.3（高风险）
        ncr = financial_block.net_profit_cash_ratio
        if ncr is not None and ncr < 0.3:
            flag = RedFlag(
                code="LOW_NET_CASH_RATIO",
                label="净现比极低（<0.3）",
                severity="RED",
                source_module="module2_financial",
                detail=f"经营现金流/净利润: {ncr:.2f}",
                numeric_value=ncr,
                threshold=0.3,
            )
            red_flags.append(flag)
            deductions["low_net_cash_ratio"] = self.DEDUCTIONS["low_net_cash_ratio"]
        # 2f. 净现比 0.3-0.5（中风险）
        elif ncr is not None and 0.3 <= ncr < 0.5:
            flag = RedFlag(
                code="MEDIUM_NET_CASH_RATIO",
                label="净现比较低（0.3-0.5）",
                severity="YELLOW",
                source_module="module2_financial",
                detail=f"经营现金流/净利润: {ncr:.2f}",
                numeric_value=ncr,
                threshold=0.5,
            )
            yellow_flags.append(flag)
            deductions["medium_net_cash_ratio"] = self.DEDUCTIONS["medium_net_cash_ratio"]

        # 2g. ROE < 行业P10（高风险）
        roe_p10 = threshold_block.roe_p10
        roe_latest = financial_block.roe_latest
        if roe_latest is not None and roe_p10 is not None and roe_latest < roe_p10:
            flag = RedFlag(
                code="LOW_ROE_VS_INDUSTRY",
                label=f"ROE低于行业P10阈值",
                severity="RED",
                source_module="industry_thresholds",
                detail=f"ROE={roe_latest:.2f}% < 行业P10={roe_p10:.2f}%（{threshold_block.industry_name}）",
                numeric_value=roe_latest,
                threshold=roe_p10,
            )
            red_flags.append(flag)
            deductions["low_roe_vs_industry"] = self.DEDUCTIONS["low_roe_vs_industry"]

        # 2h. 存货周转率持续恶化（高风险）
        if financial_block.inventory_turnover_trend is not None and financial_block.inventory_turnover_trend < -0.1:
            flag = RedFlag(
                code="INVENTORY_TURNOVER_WORSENING",
                label="存货周转率持续恶化",
                severity="RED",
                source_module="module2_financial",
                detail=f"存货周转率变化: {financial_block.inventory_turnover_trend*100:.1f}%",
                numeric_value=financial_block.inventory_turnover_trend,
            )
            red_flags.append(flag)
            deductions["inventory_turnover_worsening"] = self.DEDUCTIONS["inventory_turnover_worsening"]

        # 2i. 收入持续下滑（高风险）
        if financial_block.revenue_growth_yoy is not None and financial_block.revenue_growth_yoy < -0.1:
            flag = RedFlag(
                code="REVENUE_DECLINE",
                label="营业收入同比下滑",
                severity="RED",
                source_module="module2_financial",
                detail=f"收入同比增长: {financial_block.revenue_growth_yoy*100:.1f}%",
                numeric_value=financial_block.revenue_growth_yoy,
            )
            red_flags.append(flag)
            deductions["revenue_decline"] = self.DEDUCTIONS["revenue_decline"]

        # ── 3. 中风险黄旗（历史相关）─────────────────────────────────────

        # 3a. 历史审计非标（保留此规则，但严格条件：>=4年历史非标 且 当前干净 且 signal正常）
        # 5年以上的"带强调事项段"等非标 → 若当前干净，说明是偶发事件，不触发
        # 仅当: 历史非标类型包含"保留/无法表示/否定"时 才触发
        all_abnormal = governance_block.audit_opinions
        severe_historical = {
            y: op for y, op in all_abnormal.items()
            if op in {"保留意见", "无法表示意见", "否定意见"}
        }
        if severe_historical and governance_block.audit_score == 0:
            flag = RedFlag(
                code="AUDIT_HISTORY_NON_STANDARD",
                label="审计历史存在严重非标意见（当前已改善）",
                severity="YELLOW",
                source_module="module9_governance",
                detail=f"历史严重非标: {severe_historical}",
            )
            yellow_flags.append(flag)
            deductions["audit_history_non_standard"] = self.DEDUCTIONS["audit_history_non_standard"]

        # 3b. 收入增速放缓（中风险）
        if financial_block.revenue_growth_yoy is not None:
            if -0.1 <= financial_block.revenue_growth_yoy < 0:
                flag = RedFlag(
                    code="REVENUE_GROWTH_SLOWDOWN",
                    label="营业收入增速放缓",
                    severity="YELLOW",
                    source_module="module2_financial",
                    detail=f"收入同比增长: {financial_block.revenue_growth_yoy*100:.1f}%",
                    numeric_value=financial_block.revenue_growth_yoy,
                )
                yellow_flags.append(flag)
                deductions["revenue_growth_slowdown"] = self.DEDUCTIONS["revenue_growth_slowdown"]

        # ── 4. 计算总分 ───────────────────────────────────────────────────
        total_deduction = sum(deductions.values())
        # 极端风险钳制：总分不低于0
        overall_score = max(0, base_score + total_deduction)

        # ── 4b. 数据质量评估 ────────────────────────────────────────────
        # 判断依据：3个关键财务指标是否完整
        critical_fields = ["roe_latest", "net_profit_cash_ratio", "revenue_growth_yoy"]
        missing_critical = [
            f for f in critical_fields
            if getattr(financial_block, f, None) is None
        ]
        if len(missing_critical) >= 2:
            data_source = "degraded"
        elif len(missing_critical) == 1:
            data_source = "partial"
        else:
            data_source = "full"

        # ── 5. 综合裁定 verdict（分层判断）───────────────────────────────
        # 分层判断规则：
        #  1. 有极端红旗 → 高风险
        #  2. score < 50 → 高风险（极端差）
        #  3. 2个以上高风险红旗 → 高风险
        #  4. 1个高风险红旗 → 存疑
        #  5. 有黄旗且 score < 80 → 存疑
        #  6. score >= 80 + 数据完整 → 通过
        #  7. score >= 80 + 数据不完整 → 存疑（数据缺失，不能算通过）
        #  8. 其他 → 存疑
        if extreme_flags:
            verdict = "高风险"
        elif overall_score < 50:
            verdict = "高风险"
        elif len(red_flags) >= 2:
            verdict = "高风险"
        elif len(red_flags) == 1:
            verdict = "存疑"
        elif yellow_flags and overall_score < 80:
            verdict = "存疑"
        elif overall_score >= 80 and data_source == "full":
            verdict = "通过"
        elif overall_score >= 80 and data_source in ("partial", "degraded"):
            verdict = "存疑"
        else:
            verdict = "存疑"

        # 已知问题公司强制高风险
        if stock_code in {"600518", "002450", "300104", "600074", "002604"}:
            verdict = "高风险"

        scoring_details = {
            "base_score": base_score,
            "deductions": deductions,
            "total_deduction": total_deduction,
            "extreme_count": len(extreme_flags),
            "red_count": len(red_flags),
            "yellow_count": len(yellow_flags),
            "missing_critical": missing_critical,
        }

        return ScoredReport(
            stock_code=stock_code,
            stock_name=stock_name,
            report_date=report_date,
            verdict=verdict,
            governance=governance_block,
            financial=financial_block,
            industry_thresholds=threshold_block,
            mda=mda_block,
            announcements=announcement_block,
            overall_score=overall_score,
            red_flags=red_flags,
            yellow_flags=yellow_flags,
            extreme_flags=extreme_flags,
            scoring_details=scoring_details,
            data_source=data_source,
        )


def compute_consecutive_losses(df: pd.DataFrame) -> Tuple[int, str]:
    """
    从财务历史数据计算连续亏损年数
    返回: (consecutive_loss_years, latest_year)
    """
    if df.empty:
        return 0, ""

    # 取净利润列
    profit_col = None
    for col in ["net_profit", "净利润", "归属净利润"]:
        if col in df.columns:
            profit_col = col
            break

    if profit_col is None:
        return 0, ""

    # 按日期排序
    df = df.sort_values("statDate")
    df = df.dropna(subset=[profit_col])

    if df.empty:
        return 0, ""

    # 从最新期往前数
    loss_count = 0
    latest_year = str(df.iloc[-1].get("statDate", ""))[:4]

    for _, row in df.iloc[::-1].iterrows():
        profit = row[profit_col]
        if profit < 0:
            loss_count += 1
        else:
            break

    return loss_count, latest_year


def compute_revenue_growth(df: pd.DataFrame) -> Optional[float]:
    """计算最新一期营收同比增长率"""
    if df.empty:
        return None

    rev_col = None
    for col in ["revenue", "营业收入"]:
        if col in df.columns:
            rev_col = col
            break

    if rev_col is None:
        return None

    df = df.sort_values("statDate").dropna(subset=[rev_col])
    if len(df) < 2:
        return None

    latest = df.iloc[-1][rev_col]
    prev = df.iloc[-2][rev_col]

    if prev == 0 or pd.isna(prev):
        return None

    return (latest - prev) / abs(prev)


def compute_inventory_trend(df: pd.DataFrame) -> Optional[float]:
    """计算存货周转率趋势（近3年平均变化率）"""
    if df.empty:
        return None

    inv_col = None
    for col in ["inventory_turnover", "存货周转率", "inventory_turnover_days"]:
        if col in df.columns:
            inv_col = col
            break

    if inv_col is None:
        return None

    df = df.sort_values("statDate").dropna(subset=[inv_col])
    if len(df) < 3:
        return None

    recent = df.iloc[-3:][inv_col].values
    if recent[0] == 0 or pd.isna(recent[0]):
        return None

    # 计算相对于3年前的变化率
    change = (recent[-1] - recent[0]) / abs(recent[0])
    return change
