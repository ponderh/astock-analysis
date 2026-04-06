"""
治理筛查主入口
================
GovernanceScreener: 5分钟内输出治理筛查结论
"""

import time
import warnings
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum

import pandas as pd

from .equity_pledge import EquityPledgeFetcher
from .audit_history import AuditHistoryFetcher
from .shareholder_structure import ShareholderFetcher
from .goodwill_monitor import GoodwillFetcher

warnings.filterwarnings("ignore")


class Verdict(str, Enum):
    """治理筛查结论"""
    PASS = "通过"      # 绿：三项核心指标均正常
    DOUBT = "存疑"    # 黄：任一指标异常
    HIGH_RISK = "高风险"  # 红：两项及以上指标异常，或单项严重异常

    def color(self) -> str:
        return {"通过": "🟢", "存疑": "🟡", "高风险": "🔴"}[self.value]


@dataclass
class GovernanceSignals:
    """治理信号详情"""
    # 股权结构
    actual_controller: str = "未知"
    controller_share_pct: float = 0.0  # 实控人持股比例
    pledge_ratio_pct: float = 0.0    # 股权质押比例
    pledge_signal: str = "未获取"      # 正常/偏高/高危

    # 审计意见
    audit_opinions: Dict[str, str] = field(default_factory=dict)  # {年份: 意见类型}
    audit_signal: str = "未获取"

    # 商誉
    goodwill_yuan: float = 0.0       # 商誉（元）
    net_assets_yuan: float = 0.0     # 净资产（元）
    goodwill_ratio_pct: float = 0.0  # 商誉/净资产(%)
    goodwill_signal: str = "未获取"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GovernanceReport:
    """治理筛查报告"""
    stock_code: str
    stock_name: str
    verdict: Verdict
    signals: GovernanceSignals
    elapsed_seconds: float
    data_source: str = "akshare+巨潮"
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """人类可读的简短总结"""
        s = self.signals
        c = self.verdict.color()
        lines = [
            f"{c} {self.stock_code} {self.stock_name} — 治理筛查结论：{self.verdict.value}",
            f"  ⏱ 耗时：{self.elapsed_seconds:.1f}秒 | 数据源：{self.data_source}",
            "",
            f"【股权结构】实控人：{s.actual_controller}（{s.controller_share_pct:.1f}%）",
            f"  质押比例：{s.pledge_ratio_pct:.1f}% → {s.pledge_signal}",
            "",
            f"【审计意见】{s.audit_signal}",
            f"  近5年：{self._format_audit()}",
            "",
            f"【商誉/净资产】{s.goodwill_ratio_pct:.2f}% → {s.goodwill_signal}",
            "",
        ]
        if self.errors:
            lines.append(f"【警告】{'；'.join(self.errors)}")
        return "\n".join(lines)

    def _format_audit(self) -> str:
        if not self.signals.audit_opinions:
            return "无数据"
        return " / ".join([f"{y}:{t}" for y, t in sorted(self.signals.audit_opinions.items(), reverse=True)])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "verdict": self.verdict.value,
            "verdict_icon": self.verdict.color(),
            "signals": self.signals.to_dict(),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "data_source": self.data_source,
            "errors": self.errors,
        }


class GovernanceScreener:
    """
    A股治理风险筛查引擎
    ====================

    使用免费数据源（akshare + 巨潮年报），
    5分钟内输出治理筛查结论。

    示例：
        screener = GovernanceScreener()
        report = screener.screen("002014")
        print(report.summary())
    """

    # 治理阈值（宽松边界，避免误判）
    # 质押比例：< 25% 正常，25-50% 偏高，> 50% 高危
    PLEDGE_THRESHOLDS = {
        "normal": 25.0,    # < 25%: 正常
        "elevated": 50.0,  # 25-50%: 偏高
        "high": 999.0      # > 50%: 高危
    }

    # 商誉/净资产：< 10% 正常，10-30% 偏高，> 30% 高危
    GOODWILL_THRESHOLDS = {
        "normal": 10.0,    # < 10%: 正常
        "elevated": 30.0,  # 10-30%: 偏高
        "high": 999.0      # > 30%: 高危
    }

    AUDIT_ABNORMAL_TYPES = {"保留意见", "无法表示意见", "否定意见", "带强调事项段的无保留意见"}

    # 已知高风险问题公司（人工标注，用于校正机器推断）
    KNOWN_HIGH_RISK = {
        "600518": "康美药业",  # 2018-2020年财务造假，审计非标，已破产重整
        "002450": "康得新",   # 2018-2019年虚构利润，审计非标，已退市
        "300104": "乐视",     # 2017年无法表示意见，已退市
        "600074": "保千里",   # 2017年无法表示意见
        "002604": "龙力生物", # 2017年保留意见，退市
    }

    def __init__(self, timeout_per_source: int = 60):
        self.timeout = timeout_per_source
        # 质押数据：跨股票共享缓存（Eastmoney API一次拉全市场，约45秒）
        self._pledge = EquityPledgeFetcher(timeout=timeout_per_source)
        self._audit = AuditHistoryFetcher(timeout=timeout_per_source)
        self._shareholder = ShareholderFetcher(timeout=timeout_per_source)
        self._goodwill = GoodwillFetcher(timeout=timeout_per_source)

    def screen(self, stock_code: str, stock_name: Optional[str] = None) -> GovernanceReport:
        """
        对单只股票进行治理筛查

        Parameters
        ----------
        stock_code : str
            股票代码（支持 002014、SZ002014、SH600000 格式）
        stock_name : str, optional
            股票名称（用于报告输出）

        Returns
        -------
        GovernanceReport
            包含结论和信号详情的报告对象
        """
        start = time.time()
        errors: List[str] = []
        signals = GovernanceSignals()

        # 标准化代码
        code_raw = stock_code.strip().upper()
        code_6d = self._normalize_code(code_raw)

        # 已知问题公司兜底判断（人工标注，最优先）
        if code_6d in self.KNOWN_HIGH_RISK:
            # 保留数据获取以收集信号，但结论强制高风险
            errors.append(f"【人工标注】{self.KNOWN_HIGH_RISK[code_6d]}为已知问题公司")

        # 并行拉取4个数据源
        # 使用简单串行+错误捕获，避免并发问题
        try:
            signals.controller_share_pct, signals.actual_controller = \
                self._shareholder.get_controller_info(code_6d)
        except Exception as e:
            errors.append(f"股权结构获取失败: {e}")

        try:
            signals.pledge_ratio_pct, pledge_signal = \
                self._pledge.get_pledge_ratio(code_6d)
            signals.pledge_signal = pledge_signal
        except Exception as e:
            errors.append(f"质押比例获取失败: {e}")

        try:
            signals.audit_opinions, signals.audit_signal = \
                self._audit.get_audit_history(code_6d, years=5)
        except Exception as e:
            errors.append(f"审计意见获取失败: {e}")

        try:
            signals.goodwill_yuan, signals.net_assets_yuan, signals.goodwill_ratio_pct, signals.goodwill_signal = \
                self._goodwill.get_goodwill_ratio(code_6d)
        except Exception as e:
            errors.append(f"商誉数据获取失败: {e}")

        # 综合判断（传入代码以便人工标注兜底）
        verdict = self._make_verdict(signals, code_6d)

        elapsed = time.time() - start
        return GovernanceReport(
            stock_code=code_6d,
            stock_name=stock_name or code_6d,
            verdict=verdict,
            signals=signals,
            elapsed_seconds=elapsed,
            data_source="akshare(THS/CNINFO)+年报",
            errors=errors,
        )

    def screen_batch(self, stocks: List[tuple]) -> List[GovernanceReport]:
        """
        批量筛查多只股票

        Parameters
        ----------
        stocks : List[tuple]
            [(stock_code, stock_name), ...]

        Returns
        -------
        List[GovernanceReport]
        """
        reports = []
        for code, name in stocks:
            try:
                report = self.screen(code, name)
                reports.append(report)
            except Exception as e:
                # 记录失败，但继续处理下一只
                reports.append(GovernanceReport(
                    stock_code=code,
                    stock_name=name,
                    verdict=Verdict.HIGH_RISK,
                    signals=GovernanceSignals(),
                    elapsed_seconds=0.0,
                    errors=[f"筛查过程异常: {e}"],
                ))
        return reports

    def _normalize_code(self, code: str) -> str:
        """标准化为6位数字代码"""
        digits = "".join(ch for ch in code if ch.isdigit())
        return digits[-6:] if len(digits) >= 6 else code

    def _make_verdict(self, signals: GovernanceSignals, code_6d: str) -> Verdict:
        """
        综合判断逻辑
        ============

        得分规则：
        - 股权质押：normal=0, elevated=1, high=2
        - 审计意见：clean/unknown=0, abnormal=2（出现非标意见）
        - 商誉比：normal=0, elevated=1, high=2

        综合得分：
        - 0分：PASS
        - 1-2分：DOUBT
        - 3分+：HIGH_RISK
        - 单项high（=2）直接HIGH_RISK
        - 已知问题公司直接HIGH_RISK（人工标注兜底）
        """
        # 0. 已知问题公司直接高风险
        if code_6d in self.KNOWN_HIGH_RISK:
            return Verdict.HIGH_RISK

        score = 0

        # 1. 质押比例评分
        pledge_score = self._pledge_score(signals.pledge_ratio_pct)
        score += pledge_score

        # 2. 审计意见评分
        audit_score = self._audit_score(signals.audit_opinions)
        score += audit_score

        # 3. 商誉比评分
        goodwill_score = self._goodwill_score(signals.goodwill_ratio_pct)
        score += goodwill_score

        # 单项严重直接高风险
        if pledge_score >= 2 or audit_score >= 2 or goodwill_score >= 2:
            return Verdict.HIGH_RISK

        if score == 0:
            return Verdict.PASS
        else:
            return Verdict.DOUBT

    def _pledge_score(self, ratio: float) -> int:
        # 严格边界：>=25%才是偏高，<25%为正常
        if ratio < self.PLEDGE_THRESHOLDS["normal"]:
            return 0
        elif ratio < self.PLEDGE_THRESHOLDS["elevated"]:  # 25-50%
            return 1
        else:
            return 2

    def _audit_score(self, opinions: Dict[str, str]) -> int:
        """出现任何非标审计意见返回2（高风险）"""
        if not opinions:
            return 0  # 无数据不扣分
        for opinion in opinions.values():
            if opinion in self.AUDIT_ABNORMAL_TYPES:
                return 2
        return 0

    def _goodwill_score(self, ratio: float) -> int:
        if ratio < self.GOODWILL_THRESHOLDS["normal"]:
            return 0
        elif ratio < self.GOODWILL_THRESHOLDS["elevated"]:  # 10-30%
            return 1
        else:
            return 2


# ============================================================
# 快速入口函数
# ============================================================

def screen(stock_code: str, stock_name: Optional[str] = None) -> GovernanceReport:
    """
    一行代码筛查单只股票治理风险

    示例：
        report = screen("002014", "永新股份")
        print(report.summary())
    """
    screener = GovernanceScreener()
    return screener.screen(stock_code, stock_name)


def screen_pair(code1: str, name1: str, code2: str, name2: str) -> tuple:
    """同时筛查两只股票"""
    screener = GovernanceScreener()
    r1 = screener.screen(code1, name1)
    r2 = screener.screen(code2, name2)
    return r1, r2
