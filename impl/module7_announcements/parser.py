"""
module7_announcements.parser
===========================
公告类型分类器：
  - 业绩预告 / 业绩快报 / 业绩更正
  - 重大重组并购 / 股权激励 / 交易所问询函
  - 其他

基于关键词规则 + 正则匹配，识别准确率目标 ≥ 80%
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

# ── 公告类型枚举 ─────────────────────────────────────────────────────────────

class NoticeType(Enum):
    UNKNOWN = "unknown"
    # P0 类型
    YJYG = "业绩预告"       # 业绩预告
    YJKB = "业绩快报"       # 业绩快报
    YJGG = "业绩更正"       # 业绩更正/修正
    # P1 类型
    CZJL = "重大重组"       # 重大重组/并购
    GQJL = "股权激励"       # 股权激励
    WTH = "问询函"          # 交易所问询函
    # 其他
    NCGJ = "日常公告"        # 日常公告
    FXTX = "风险提示"       # 风险提示
    QITG = "其他公告"        # 其他


# ── 分类规则 ─────────────────────────────────────────────────────────────────

# 每个类型定义：(正则模式列表, 置信度权重)
# 匹配时按序检查，返回第一个命中的类型

_TYPE_PATTERNS: list[tuple[NoticeType, list[re.Pattern], float]] = [
    (
        NoticeType.YJGG,
        [
            re.compile(r"业绩更正", re.I),
            re.compile(r"业绩修正", re.I),
            re.compile(r"业绩差异", re.I),
            re.compile(r"业绩调整", re.I),
            re.compile(r"补充更正", re.I),
            re.compile(r"差错更正", re.I),
            re.compile(r"会计差错", re.I),
        ],
        0.95,
    ),
    (
        NoticeType.YJYG,
        [
            re.compile(r"业绩预告", re.I),
            re.compile(r"年度业绩预告", re.I),
            re.compile(r"一季度业绩预告", re.I),
            re.compile(r"半年度业绩预告", re.I),
            re.compile(r"前三季度业绩预告", re.I),
            re.compile(r"业绩大幅上升", re.I),
            re.compile(r"业绩大幅下降", re.I),
            re.compile(r"扭亏为盈", re.I),
            re.compile(r"首亏|续亏|增亏|减亏", re.I),
            re.compile(r"业绩预盈", re.I),
            re.compile(r"业绩预亏", re.I),
        ],
        0.90,
    ),
    (
        NoticeType.YJKB,
        [
            re.compile(r"业绩快报", re.I),
            re.compile(r"年度业绩快报", re.I),
            re.compile(r"半年度业绩快报", re.I),
            re.compile(r"业绩快报", re.I),
        ],
        0.90,
    ),
    (
        NoticeType.CZJL,
        [
            re.compile(r"重大资产重组", re.I),
            re.compile(r"发行股份购买资产", re.I),
            re.compile(r"重大重组", re.I),
            re.compile(r"资产重组", re.I),
            re.compile(r"收购股权", re.I),
            re.compile(r"并购重组", re.I),
            re.compile(r"吸收合并", re.I),
            re.compile(r"发行股份", re.I),
            re.compile(r"募资收购", re.I),
            re.compile(r"控制权变更", re.I),
            re.compile(r"要约收购", re.I),
        ],
        0.85,
    ),
    (
        NoticeType.GQJL,
        [
            re.compile(r"股权激励", re.I),
            re.compile(r"限制性股票", re.I),
            re.compile(r"股票期权", re.I),
            re.compile(r"员工持股计划", re.I),
            re.compile(r"激励计划", re.I),
        ],
        0.85,
    ),
    (
        NoticeType.WTH,
        [
            re.compile(r"问询函", re.I),
            re.compile(r"交易所问询", re.I),
            re.compile(r"监管问询", re.I),
            re.compile(r"关注函", re.I),
            re.compile(r"重组问询", re.I),
            re.compile(r"审核问询", re.I),
            re.compile(r"补充问询", re.I),
        ],
        0.90,
    ),
    (
        NoticeType.FXTX,
        [
            re.compile(r"风险提示", re.I),
            re.compile(r"退市风险", re.I),
            re.compile(r"暂停上市", re.I),
            re.compile(r"终止上市", re.I),
            re.compile(r"特别处理", re.I),
            re.compile(r"ST公告", re.I),
        ],
        0.80,
    ),
]


# ── 解析结果数据结构 ─────────────────────────────────────────────────────────

@dataclass
class ParsedNotice:
    """解析后的公告条目"""
    title: str
    notice_date: str
    column_name: str
    stock_code: str = ""
    short_name: str = ""
    notice_type: NoticeType = NoticeType.UNKNOWN
    type_confidence: float = 0.0
    type_label: str = "unknown"
    # 提取的关键字段
    extracted_amount: Optional[str] = None      # 业绩金额
    extracted_change_pct: Optional[str] = None  # 变动百分比
    extracted_period: Optional[str] = None       # 报告期
    source: str = ""
    art_code: str = ""
    url: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "stock_code": self.stock_code,
            "short_name": self.short_name,
            "notice_date": self.notice_date[:10] if self.notice_date else "",
            "title": self.title,
            "column_name": self.column_name,
            "notice_type": self.type_label,
            "type_confidence": self.type_confidence,
            "notice_type_enum": self.notice_type.value,
            "extracted_amount": self.extracted_amount,
            "extracted_change_pct": self.extracted_change_pct,
            "extracted_period": self.extracted_period,
            "source": self.source,
            "art_code": self.art_code,
            "url": self.url,
        }


# ── 核心分类函数 ─────────────────────────────────────────────────────────────

def classify_notice(title: str, column_name: str = "") -> tuple[NoticeType, float]:
    """
    根据标题和栏目名称分类公告

    Returns:
        (NoticeType, confidence)
    """
    text = f"{title} {column_name}"

    for notice_type, patterns, base_confidence in _TYPE_PATTERNS:
        for pattern in patterns:
            if pattern.search(text):
                return notice_type, base_confidence

    return NoticeType.UNKNOWN, 0.0


# ── 业绩预告关键字段提取 ─────────────────────────────────────────────────────

_YJYG_AMOUNT_PATTERNS = [
    # 归母净利润范围
    re.compile(r"归母净利润[:：]?\s*([\d\.]+)\s*~?\s*([\d\.]+)?\s*亿元", re.I),
    re.compile(r"归属于上市公司股东的净利润[:：]?\s*([\d\.,～~至]+)\s*(?:亿元|万)?", re.I),
    # 单值
    re.compile(r"归母净利润[:：]?\s*([+-]?[\d\.]+)\s*(?:亿元|万)", re.I),
    # 变动百分比
    re.compile(r"(?:同比增长|同比下降|增长|下降)[：:\s]*([+-]?[\d\.]+)%", re.I),
    re.compile(r"变动幅度[:：]\s*([+-]?[\d\.]+)%", re.I),
    # 报告期
    re.compile(r"(20\d{2})[-年](?:半年度|前三季度|年度|一季度|[1-4]季度)", re.I),
    re.compile(r"(?:202[4-9]|203[0-9])年度业绩预告", re.I),
]

_AMOUNT_VALUE_RE = re.compile(r"([\d\.]+)\s*(?:~|～|至)\s*([\d\.]+)\s*(?:亿元|万)")
_SINGLE_AMOUNT_RE = re.compile(r"([+-]?[\d\.]+)\s*(?:亿元|万)")
_CHANGE_PCT_RE = re.compile(r"([+-]?[\d\.]+)%")


def extract_yjyg_fields(title: str) -> dict:
    """从业绩预告标题提取关键字段"""
    result = {
        "extracted_amount": None,
        "extracted_change_pct": None,
        "extracted_period": None,
    }

    # 提取金额
    m = _AMOUNT_VALUE_RE.search(title)
    if m:
        result["extracted_amount"] = f"{m.group(1)}~{m.group(2)}亿元"

    m2 = _SINGLE_AMOUNT_RE.search(title)
    if m2 and not result["extracted_amount"]:
        result["extracted_amount"] = f"{m2.group(1)}亿元"

    # 提取变动百分比
    pct_matches = _CHANGE_PCT_RE.findall(title)
    if pct_matches:
        result["extracted_change_pct"] = "%".join(pct_matches[:2]) + "%"

    # 提取报告期
    period_m = re.search(r"(20\d{2})[-年]?(?:半年度|前三季度|年度|[1-4]季度)", title)
    if period_m:
        result["extracted_period"] = period_m.group(0)

    return result


# ── 批量解析 ────────────────────────────────────────────────────────────────

def parse_notices(raw_notices: list[dict]) -> list[ParsedNotice]:
    """
    批量解析原始公告列表

    Args:
        raw_notices: fetcher.fetch_announcements() 返回的原始列表

    Returns:
        ParsedNotice 列表
    """
    parsed = []
    for raw in raw_notices:
        title = raw.get("title", "")
        column_name = raw.get("column_name", "")
        notice_type, confidence = classify_notice(title, column_name)

        item = ParsedNotice(
            title=title,
            notice_date=raw.get("notice_date", ""),
            column_name=column_name,
            stock_code=raw.get("stock_code", ""),
            short_name=raw.get("short_name", ""),
            notice_type=notice_type,
            type_confidence=confidence,
            type_label=notice_type.value,
            source=raw.get("source", ""),
            art_code=raw.get("art_code", ""),
            url=raw.get("url", ""),
            raw=raw,
        )

        # 业绩预告额外字段提取
        if notice_type in (NoticeType.YJYG, NoticeType.YJKB, NoticeType.YJGG):
            yjyg_fields = extract_yjyg_fields(title)
            item.extracted_amount = yjyg_fields["extracted_amount"]
            item.extracted_change_pct = yjyg_fields["extracted_change_pct"]
            item.extracted_period = yjyg_fields["extracted_period"]

        parsed.append(item)

    return parsed


def get_notices_by_type(
    parsed_notices: list[ParsedNotice],
    notice_types: list[NoticeType],
) -> list[ParsedNotice]:
    """筛选特定类型的公告"""
    return [n for n in parsed_notices if n.notice_type in notice_types]


# ── 分类统计报告 ────────────────────────────────────────────────────────────

def classification_report(parsed_notices: list[ParsedNotice]) -> dict:
    """生成分类统计报告"""
    type_counts: dict[str, int] = {}
    type_counts_confident: dict[str, int] = {}

    for n in parsed_notices:
        label = n.type_label
        type_counts[label] = type_counts.get(label, 0) + 1
        if n.type_confidence >= 0.80:
            type_counts_confident[label] = type_counts_confident.get(label, 0) + 1

    total = len(parsed_notices)
    confident_total = sum(type_counts_confident.values())
    avg_confidence = (
        sum(n.type_confidence for n in parsed_notices) / total if total > 0 else 0
    )

    return {
        "total": total,
        "by_type": type_counts,
        "confident_by_type": type_counts_confident,
        "high_confidence_count": confident_total,
        "high_confidence_rate": confident_total / total if total > 0 else 0,
        "avg_confidence": avg_confidence,
    }


if __name__ == "__main__":
    # 快速测试
    test_titles = [
        "永新股份：2024年度业绩预告",
        "永新股份：2024年度业绩快报",
        "永新股份：关于2024年年度报告的业绩更正公告",
        "永新股份：关于股权激励计划草案的公告",
        "永新股份：关于收到交易所问询函的公告",
        "永新股份：2026年第一季度可转换公司债券转股情况的公告",
    ]
    for t in test_titles:
        nt, conf = classify_notice(t)
        print(f"[{nt.value}] ({conf:.0%}) {t}")
