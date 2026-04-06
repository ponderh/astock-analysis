"""
module7_announcements.api
=========================
公告数据管道 API 接口层

提供简洁的业务接口，封装 fetcher + parser
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fetcher import fetch_announcements, fetch_notice_detail
from parser import (
    NoticeType,
    ParsedNotice,
    parse_notices,
    classification_report,
    get_notices_by_type,
)


# ── 主接口 ──────────────────────────────────────────────────────────────────


def fetch_notices(stock_code: str, last_fetch_time: Optional[str] = None) -> list[dict]:
    """
    增量抓取接口，专为 cron 场景设计。
    仅返回 last_fetch_time 之后的最新公告。

    Args:
        stock_code: 股票代码，如 "002014"
        last_fetch_time: ISO 日期字符串 "YYYY-MM-DD" 或 "YYYY-MM-DD HH:MM:SS"
                         如果为 None，返回所有公告（等同于全量抓取）

    Returns:
        list[dict]: 原始公告列表（未解析），按 notice_date 降序
                    每条包含: art_code, title, notice_date, column_name,
                    stock_code, short_name, source, url
    """
    if last_fetch_time:
        # 解析 last_fetch_time，支持 "YYYY-MM-DD" 和 "YYYY-MM-DD HH:MM:SS"
        try:
            if len(last_fetch_time) == 10:
                last_dt = datetime.strptime(last_fetch_time, "%Y-%m-%d")
            else:
                last_dt = datetime.strptime(last_fetch_time, "%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            logger.warning("[fetch_notices] last_fetch_time 格式错误: %s", e)
            last_dt = None
    else:
        last_dt = None

    # 全量抓取（begin_time 设为极早期，确保覆盖所有公告，
    # 过滤在下面通过 last_fetch_time 完成）
    begin_time = "2000-01-01" if last_dt else None

    raw_notices = fetch_announcements(
        stock_code=stock_code,
        begin_time=begin_time,
        end_time=None,  # 到现在
        max_notices=500,  # 增量场景也抓多一些，防止漏掉
    )

    if last_dt:
        filtered = []
        for n in raw_notices:
            notice_date_str = n.get("notice_date", "")
            if not notice_date_str:
                continue
            # notice_date 格式: "YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DD"
            try:
                if len(notice_date_str) >= 19:
                    notice_dt = datetime.strptime(notice_date_str[:19], "%Y-%m-%d %H:%M:%S")
                else:
                    notice_dt = datetime.strptime(notice_date_str[:10], "%Y-%m-%d")
                if notice_dt > last_dt:
                    filtered.append(n)
            except ValueError:
                continue
        return filtered

    return raw_notices


def get_announcements(
    stock_code: str,
    begin_time: Optional[str] = None,
    end_time: Optional[str] = None,
    max_notices: int = 50,
    notice_types: Optional[list[str]] = None,
    min_confidence: float = 0.0,
) -> dict:
    """
    获取并解析股票公告

    Args:
        stock_code: 股票代码，如 "002014"
        begin_time: 开始日期 "YYYY-MM-DD"
        end_time: 结束日期 "YYYY-MM-DD"
        max_notices: 最大返回条数
        notice_types: 过滤的公告类型，如 ["业绩预告", "业绩快报"]
                    可选值：业绩预告, 业绩快报, 业绩更正, 重大重组, 股权激励, 问询函
        min_confidence: 最低置信度阈值

    Returns:
        {
            "success": bool,
            "stock_code": str,
            "total_raw": int,
            "total_parsed": int,
            "notices": [ParsedNotice.to_dict(), ...],
            "report": classification_report,
            "sources": {source: count, ...},
            "error": str or None,
        }
    """
    try:
        # 1. 抓取原始数据
        raw_notices = fetch_announcements(
            stock_code=stock_code,
            begin_time=begin_time,
            end_time=end_time,
            max_notices=max_notices,
        )

        # 2. 解析分类
        parsed = parse_notices(raw_notices)

        # 3. 按类型过滤
        if notice_types:
            type_enums = []
            for t in notice_types:
                for et in NoticeType:
                    if et.value == t or t in et.value:
                        type_enums.append(et)
            if type_enums:
                parsed = get_notices_by_type(parsed, type_enums)

        # 4. 按置信度过滤
        if min_confidence > 0:
            parsed = [n for n in parsed if n.type_confidence >= min_confidence]

        # 5. 生成分类报告
        report = classification_report(parsed)

        # 6. 统计来源
        sources: dict[str, int] = {}
        for n in parsed:
            src = n.source or "unknown"
            sources[src] = sources.get(src, 0) + 1

        return {
            "success": True,
            "stock_code": stock_code,
            "total_raw": len(raw_notices),
            "total_parsed": len(parsed),
            "notices": [n.to_dict() for n in parsed],
            "report": report,
            "sources": sources,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "stock_code": stock_code,
            "total_raw": 0,
            "total_parsed": 0,
            "notices": [],
            "report": {},
            "sources": {},
            "error": str(e),
        }


logger = logging.getLogger(__name__)


def get_yjyg_notices(
    stock_code: str,
    begin_time: Optional[str] = None,
    end_time: Optional[str] = None,
    years: Optional[list[int]] = None,
) -> list[dict]:
    """
    获取业绩预告/快报/更正公告（简写接口）

    Args:
        stock_code: 股票代码
        begin_time: 开始日期
        end_time: 结束日期
        years: 只返回特定年份，如 [2023, 2024, 2025]

    Returns:
        [{notice_date, title, type_label, extracted_amount, extracted_change_pct, url}, ...]
    """
    result = get_announcements(
        stock_code=stock_code,
        begin_time=begin_time,
        end_time=end_time,
        notice_types=["业绩预告", "业绩快报", "业绩更正"],
        max_notices=100,
        min_confidence=0.80,
    )

    notices = result.get("notices", [])

    if years:
        filtered = []
        for n in notices:
            date_str = n.get("notice_date", "")[:4]
            if date_str.isdigit() and int(date_str) in years:
                filtered.append(n)
        notices = filtered

    return notices


def get_latest_notices(
    stock_code: str,
    count: int = 10,
    notice_types: Optional[list[str]] = None,
) -> list[dict]:
    """
    获取最近 N 条公告（简写接口）
    """
    result = get_announcements(
        stock_code=stock_code,
        max_notices=count * 3,  # 多抓一些确保有足够结果
        notice_types=notice_types,
    )
    notices = result.get("notices", [])[:count]
    return notices


# ── 导出 ─────────────────────────────────────────────────────────────────────

__all__ = [
    "fetch_notices",
    "get_announcements",
    "get_yjyg_notices",
    "get_latest_notices",
    "NoticeType",
    "ParsedNotice",
    "fetch_announcements",
    "fetch_notice_detail",
    "parse_notices",
    "classification_report",
]
