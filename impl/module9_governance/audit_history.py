"""
审计意见历史
=============
数据源策略（4级降级）：
1. akshare stock_financial_abstract（推断）
2. 年报PDF关键词提取（需要PDF下载模块）
3. 已知问题公司数据库（硬编码案例）
4. 财务指标反推（Rule-based inference）

审计意见类型：
- 标准无保留意见：正常
- 带强调事项段的无保留意见：存疑
- 保留意见：高风险
- 无法表示意见：高风险
- 否定意见：高风险

判断逻辑：
- 有非标意见记录 → 直接引用
- 无数据但财务健康（ROE>0、净利润>0、无连续亏损）→ 推断为"正常"
- 无数据且财务异常 → 标注"需核实"
"""

import datetime
from typing import Dict, Tuple, List
import pandas as pd

try:
    import akshare as ak
    AKSHARE_OK = True
except ImportError:
    AKSHARE_OK = False


AUDIT_NORMAL = "标准无保留意见"
AUDIT_EMPHASIS = "带强调事项段的无保留意见"
AUDIT_RESERVE = "保留意见"
AUDIT_DISCLAIM = "无法表示意见"
AUDIT_ADVERSE = "否定意见"
AUDIT_UNKNOWN = "需核实"
AUDIT_NO_DATA = "数据未获取"

AUDIT_ABNORMAL = {AUDIT_RESERVE, AUDIT_DISCLAIM, AUDIT_ADVERSE, AUDIT_EMPHASIS}


# ============================================================
# 已知高风险公司审计意见数据库（用于快速匹配）
# 格式：{股票代码6位: {年份: 审计意见}}
# ============================================================
KNOWN_AUDIT_CASES: Dict[str, Dict[str, str]] = {
    # 康美药业：巨额财务造假，2018-2020连续非标
    "600518": {
        "2018": AUDIT_RESERVE,
        "2019": AUDIT_DISCLAIM,
        "2020": AUDIT_DISCLAIM,
        "2021": AUDIT_DISCLAIM,
        "2022": "停牌/退市",
    },
    # 康得新：虚构利润，2018-2019非标
    "002450": {
        "2018": AUDIT_DISCLAIM,
        "2019": AUDIT_DISCLAIM,
        "2020": "退市",
    },
    # 獐子岛：扇贝跑了，2018保留意见
    "002069": {
        "2018": AUDIT_RESERVE,
        "2019": AUDIT_EMPHASIS,
        "2020": AUDIT_NORMAL,  # 换审计机构后恢复
    },
    # 乐视：连续亏损，2017无法表示意见
    "300104": {
        "2017": AUDIT_DISCLAIM,
        "2018": "退市",
    },
}


def _get_recent_years(n: int = 5) -> List[str]:
    """返回近n年的年份字符串列表（由新到旧）"""
    year = datetime.datetime.now().year
    return [str(year - i) for i in range(n)]


class AuditHistoryFetcher:
    """审计意见历史获取器（四级降级）"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._cache: Dict[str, pd.DataFrame] = {}

    def get_audit_history(self, stock_code: str, years: int = 5) -> Tuple[Dict[str, str], str]:
        """
        获取近N年的审计意见历史

        Returns
        -------
        (opinions: Dict[str, str], signal: str)
            opinions: {年份: 审计意见类型}
            signal: 正常 / 存疑 / 高风险 / 需核实
        """
        code6d = stock_code.zfill(6)
        opinions: Dict[str, str] = {}
        recent_years = _get_recent_years(years)

        # 第一优先：已知问题公司数据库（注入所有历史记录，不受窗口限制）
        if code6d in KNOWN_AUDIT_CASES:
            known = KNOWN_AUDIT_CASES[code6d]
            # 直接合并所有已知历史记录（覆盖全时间线，不受years窗口限制）
            for y, opinion in known.items():
                opinions[y] = opinion  # e.g. 2018/2019/2020 非标意见会直接注入
            # 近N年无记录但已知库有记录的年份，标记为"历史非标"
            for y in recent_years:
                if y not in known:
                    opinions[y] = AUDIT_UNKNOWN  # 需要核实（审计推断兜底）

        # 第二优先：财务指标推断（对健康公司有效）
        inferred = self._infer_from_financials(code6d, recent_years)
        for y, op in inferred.items():
            if y not in opinions:
                opinions[y] = op

        # 标记所有仍未获取的年份
        for y in recent_years:
            if y not in opinions:
                opinions[y] = AUDIT_NO_DATA

        signal = self._signal_from_opinions(opinions)
        return opinions, signal

    def _infer_from_financials(self, stock_code: str, years: List[str]) -> Dict[str, str]:
        """
        基于财务指标推断审计意见
        仅用于：已知健康的上市公司，且akshare无法直接获取审计意见时
        """
        inferred: Dict[str, str] = {}
        if not AKSHARE_OK:
            return inferred

        try:
            df = ak.stock_financial_abstract(symbol=stock_code)
        except Exception:
            return inferred

        if df is None or df.empty:
            return inferred

        rows = {
            "净资产收益率(ROE)": "roe",
            "净利润": "net_profit",
            "扣非净利润": "ex_profit",
            "股东权益合计(净资产)": "net_assets",
        }

        year_data = {}  # {年份: {指标名: 值}}

        for label, key in rows.items():
            mask = df["指标"] == label
            if not mask.any():
                continue
            row = df[mask].iloc[0]

            for year in years:
                if year not in year_data:
                    year_data[year] = {}
                # 匹配 YYYY1231 或 YYYY0331 等报表日期
                date_cols = [c for c in df.columns[2:] if str(c).startswith(year)]
                if not date_cols:
                    continue
                col = date_cols[0]
                if col not in row.index:
                    continue
                try:
                    year_data[year][key] = float(row[col])
                except (TypeError, ValueError):
                    pass

        # 推断逻辑
        for year, data in year_data.items():
            roe = data.get("roe", None)
            profit = data.get("net_profit", None)
            ex_profit = data.get("ex_profit", None)

            # 严重亏损 → 可能非标
            if roe is not None and roe < -20.0:
                inferred[year] = AUDIT_RESERVE
            elif profit is not None and profit < -5e8:  # 亏损超5亿
                if year not in inferred:
                    inferred[year] = AUDIT_EMPHASIS
            # 扣非持续亏损 → 可能有强调事项段
            elif ex_profit is not None and ex_profit < -1e8:
                if year not in inferred:
                    inferred[year] = AUDIT_EMPHASIS
            # 正常盈利公司 → 推断为标准无保留
            elif profit is not None and profit > 0:
                inferred[year] = AUDIT_NORMAL
            # 其他情况
            else:
                if year not in inferred:
                    inferred[year] = AUDIT_UNKNOWN

        return inferred

    def _signal_from_opinions(self, opinions: Dict[str, str]) -> str:
        """
        从审计意见字典判断信号

        规则（修正版）：
        - 全量历史中有"保留/无法表示/否定意见" → 高风险（不只看近3年）
        - 全量历史中有"带强调事项段" → 存疑
        - 全量历史全是"标准无保留意见" → 正常
        - 有"需核实"或"数据未获取"但无非标 → 需核实
        - 有"停牌/退市"但无非标 → 停牌（不作为非标处理）
        """
        uncertain = {AUDIT_UNKNOWN, AUDIT_NO_DATA, "需核实", "停牌/退市"}

        # 有严重非标（检查全量历史，不限于近3年）
        for opinion in opinions.values():
            if opinion in {AUDIT_RESERVE, AUDIT_DISCLAIM, AUDIT_ADVERSE}:
                return "高风险"
        # 有强调事项段
        for opinion in opinions.values():
            if opinion == AUDIT_EMPHASIS:
                return "存疑"

        # 无非标，看是否有需核实
        non_normal = [op for op in opinions.values() if op not in uncertain]
        if non_normal:
            # 有明确意见但无非标
            if all(op == AUDIT_NORMAL for op in non_normal):
                # 若全是正常，只有需核实/无数据 → 正常
                return "正常"
        # 有需核实但无明确非标
        return "需核实"
