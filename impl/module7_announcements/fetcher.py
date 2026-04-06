"""
module7_announcements.fetcher
============================
3级降级公告抓取器：
  1. 巨潮资讯 cninfo API（需要正确的 stock 参数格式: 代码,orgId）
  2. 东方财富 np-anotice API（按日期返回，需要客户端按代码过滤）
     ⚠️ 注意：东方财富 API 仅返回最近约14天的公告，总上限约50000条。
     EM **不适宜作为主要备选数据源**，仅适合做**补充数据源**（补充近期未爬到的条目）。
     长期建议：寻找第二个全覆盖数据源（如巨潮付费API或sina财经）。
  3. AKShare（brotli 问题，作为最终降级）

Author: P0W4 Implementation
"""

from __future__ import annotations

import math
import time
import requests
from datetime import datetime, date
from typing import Optional
from functools import lru_cache

# ── 日志 ────────────────────────────────────────────────────────────────────
import logging

logger = logging.getLogger(__name__)

# ── 工具函数 ──────────────────────────────────────────────────────────────────
def _get_exchange(stock_code: str) -> str:
    """根据股票代码判断交易所

    - 沪市：6开头（600xxx, 601xxx, 603xxx等）
    - 深市：0/3开头（000xxx, 002xxx, 300xxx）
    """
    if stock_code.startswith('6'):
        return 'sse'   # 上海证券交易所
    elif stock_code.startswith(('0', '3')):
        return 'szse'  # 深圳证券交易所
    else:
        return 'szse'  # 默认深圳


# ── 常量 ────────────────────────────────────────────────────────────────────
EAST_MONEY_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
CNINFO_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

HEADERS_EM = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://data.eastmoney.com/",
}

HEADERS_CN = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "http://www.cninfo.com.cn/new/disclosure/stock?stockCode=002014",
}

# ── cninfo orgId 缓存（从 cninfo JSON 获取）─────────────────────────────────

CNINFO_ORGID_CACHE: dict[str, str] = {}

CNINFO_SEARCH_API = "http://www.cninfo.com.cn/new/information/topSearch/query"


def _get_cninfo_orgid(stock_code: str) -> Optional[str]:
    """
    获取股票代码对应的 orgId。

    orgId 格式如：gssz0002014（深圳）、gssh0600036（沪市）、9900002221（保险等特殊）

    策略：
    1. 优先从缓存获取
    2. 使用 cninfo topSearch API 查询（最可靠，可获取任意股票 orgId）
    3. Fallback 直接构造（仅适用部分沪市股票，格式：gssh + 6位代码）
    """
    stock_code = stock_code.zfill(6)

    if stock_code in CNINFO_ORGID_CACHE:
        return CNINFO_ORGID_CACHE[stock_code]

    # ── 方案1：topSearch API（最可靠） ─────────────────────────────────
    try:
        resp = requests.post(
            CNINFO_SEARCH_API,
            data={"keyWord": stock_code, "maxSecNum": "1", "maxAnnNum": "1"},
            headers={
                **HEADERS_CN,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "http://www.cninfo.com.cn/new/disclosure/stock",
            },
            timeout=10,
        )
        results = resp.json()
        if results and isinstance(results, list) and len(results) > 0:
            # 精确匹配代码
            for item in results:
                if item.get("code") == stock_code and item.get("category") == "A股":
                    orgid = item.get("orgId", "")
                    if orgid:
                        CNINFO_ORGID_CACHE[stock_code] = orgid
                        logger.debug("[CNINFO] topSearch stock %s -> orgId %s", stock_code, orgid)
                        return orgid
    except Exception as e:
        logger.warning("[CNINFO] topSearch orgId 查询失败: %s", e)

    # ── 方案2：直接构造 orgId（Fallback for 沪市） ──────────────────────────
    # 已知格式：gssh + 6位代码（例：gssh0600036 招商银行）
    # 注意：部分沪市股票（如保险类 601318）使用纯数字 orgId，无法构造
    if stock_code.startswith("6"):
        constructed = f"gssh{stock_code}"
        logger.debug("[CNINFO] fallback 直接构造 orgId: %s", constructed)
        # 不缓存未知是否有效的构造值，仅返回
        return constructed

    return None


# ── 解析函数 ─────────────────────────────────────────────────────────────────

def _em_parse_notice(item: dict) -> dict:
    """解析东方财富公告条目"""
    codes = item.get("codes", [])
    primary = codes[0] if codes else {}
    # 找 A 股代码
    a_code = None
    for c in codes:
        if c.get("ann_type", "").startswith("A"):
            a_code = c
            break
    if a_code is None and codes:
        a_code = codes[0]

    notice_date = item.get("notice_date", "") or item.get("sort_date", "")
    if isinstance(notice_date, str) and len(notice_date) == 10:
        notice_date += " 00:00:00"

    columns = item.get("columns", [])
    col_name = columns[0].get("column_name", "") if columns else ""

    return {
        "art_code": item.get("art_code", ""),
        "title": item.get("title", "") or item.get("title_ch", ""),
        "notice_date": notice_date,
        "column_name": col_name,
        "stock_code": a_code.get("stock_code", "") if a_code else "",
        "short_name": a_code.get("short_name", "") if a_code else "",
        "ann_type": a_code.get("ann_type", "") if a_code else "",
        "source": "eastmoney",
        "url": (
            f"https://data.eastmoney.com/notices/detail/"
            f"{a_code.get('stock_code', '')}/{item.get('art_code', '')}.html"
            if a_code else ""
        ),
    }


def _cninfo_parse_notice(item: dict) -> dict:
    """解析巨潮资讯公告条目"""
    ts = item.get("announcementTime", 0)
    if ts:
        ts = ts / 1000
        notice_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    else:
        notice_date = ""

    return {
        "art_code": item.get("announcementId", ""),
        "title": item.get("announcementTitle", ""),
        "notice_date": notice_date,
        "column_name": item.get("categoryName", "") or item.get("category", ""),
        "stock_code": item.get("secCode", ""),
        "short_name": item.get("secName", ""),
        "ann_type": item.get("apiSentiment", ""),
        "source": "cninfo",
        "url": item.get("adjunctUrl", ""),
    }


# ── 数据源1: 巨潮资讯 ────────────────────────────────────────────────────────

def fetch_cninfo_announcements(
    stock_code: str,
    begin_time: Optional[str] = None,
    end_time: Optional[str] = None,
    page_size: int = 30,
    max_pages: int = 20,
) -> list[dict]:
    """
    巨潮资讯公告 API
    关键：使用 stock=代码,orgId 参数（不是 secid）

    Returns:
        [{art_code, title, notice_date, column_name, stock_code, short_name, ann_type, source, url}, ...]
    """
    if not end_time:
        end_time = datetime.now().strftime("%Y-%m-%d")
    if not begin_time:
        begin_time = "2020-01-01"  # 默认查所有历史

    # 获取 orgId
    orgid = _get_cninfo_orgid(stock_code)
    if not orgid:
        logger.warning("[CNINFO] 找不到 orgId，stock_code=%s", stock_code)
        return []

    stock_param = f"{stock_code.zfill(6)},{orgid}"
    logger.info("[CNINFO] stock_param=%s", stock_param)

    # 日期范围格式: YYYY-MM-DD~YYYY-MM-DD
    se_date = f"{begin_time}~{end_time}"

    all_results: list[dict] = []
    seen_ids: set[str] = set()

    for page_idx in range(1, max_pages + 1):
        params = {
            "pageNum": str(page_idx),
            "pageSize": str(page_size),
            "column": _get_exchange(stock_code),
            "tabName": "fulltext",
            "plate": "",
            "stock": stock_param,
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": se_date,
            "sortName": "openMarkDate",
            "sortType": "desc",
            "isHLtitle": "true",
        }

        try:
            resp = requests.post(
                CNINFO_URL, data=params, headers=HEADERS_CN, timeout=20
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("[CNINFO] 请求失败 page %d: %s", page_idx, e)
            break

        total = data.get("totalRecordNum", 0)
        notices = data.get("announcements") or []

        if not notices:
            break

        for item in notices:
            parsed = _cninfo_parse_notice(item)
            aid = parsed["art_code"]
            if aid and aid not in seen_ids:
                seen_ids.add(aid)
                all_results.append(parsed)

        logger.debug(
            "[CNINFO] page %d: got %d items, total=%d", page_idx, len(notices), total
        )

        if len(all_results) >= total:
            break

        time.sleep(0.5)  # 礼貌性延迟，避免触发限流

    logger.info("[CNINFO] 股票 %s 共获取 %d 条公告（总 %d）", stock_code, len(all_results), total)
    return all_results


# ── 数据源2: 东方财富 ────────────────────────────────────────────────────────

def fetch_em_announcements(
    stock_code: str,
    begin_time: Optional[str] = None,
    end_time: Optional[str] = None,
    page_size: int = 100,
    max_pages: int = 50,
    notice_type: str = "全部",
) -> list[dict]:
    """
    东方财富 np-anotice API
    注意：此 API 不支持服务端按 stock_code 过滤，需要客户端过滤。
    ⚠️ API 仅返回最近约14天的公告（总上限约50000条）。
    ⚠️ EM 不适宜作为主要备选数据源，仅适合做**补充数据源**（补充近期未爬到的条目）。
    """

    report_map = {
        "全部": "0",
        "财务报告": "1",
        "融资公告": "2",
        "风险提示": "3",
        "信息变更": "4",
        "重大事项": "5",
        "资产重组": "6",
        "持股变动": "7",
    }
    f_node = report_map.get(notice_type, "0")

    if not end_time:
        end_time = datetime.now().strftime("%Y-%m-%d")
    if not begin_time:
        begin_time = "2020-01-01"

    all_results: list[dict] = []
    seen_codes: set[str] = set()
    target_code = stock_code.zfill(6)

    for page_idx in range(1, max_pages + 1):
        params = {
            "sr": "-1",
            "page_size": str(page_size),
            "page_index": str(page_idx),
            "ann_type": "A",
            "client_source": "web",
            "f_node": f_node,
            "s_node": "0",
            "begin_time": begin_time,
            "end_time": end_time,
        }
        try:
            resp = requests.get(EAST_MONEY_URL, params=params, headers=HEADERS_EM, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("[EM] 请求失败 page %d: %s", page_idx, e)
            break

        result = data.get("data", {})
        total_hits = result.get("total_hits", 0)
        notices = result.get("list", [])

        if not notices:
            break

        for item in notices:
            parsed = _em_parse_notice(item)
            # 按 stock_code 过滤
            if parsed["stock_code"] == target_code:
                key = parsed["art_code"]
                if key and key not in seen_codes:
                    seen_codes.add(key)
                    all_results.append(parsed)

        if page_idx * page_size >= total_hits:
            break

        time.sleep(0.2)

    logger.info(
        "[EM] 股票 %s 共获取 %d 条公告（扫描 %d 页，总 hit %d）",
        stock_code, len(all_results), page_idx, total_hits
    )
    return all_results


# ── 数据源3: AKShare 降级 ───────────────────────────────────────────────────

def fetch_akshare_announcements(
    stock_code: str,
    begin_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> list[dict]:
    """
    AKShare stock_zh_a_disclosure_report_cninfo 降级
    注意：由于 Brotli 压缩问题，可能失败
    """
    try:
        import akshare as ak

        if not end_time:
            end_time = datetime.now().strftime("%Y%m%d")
        if not begin_time:
            begin_time = "20200101"

        # 推断市场
        if stock_code.startswith(("0", "3", "002", "003")):
            market = "沪深京"
        elif stock_code.startswith("6"):
            market = "沪深京"
        else:
            market = "沪深京"

        df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=stock_code,
            market=market,
            start_date=begin_time,
            end_date=end_time,
        )

        records = []
        for _, row in df.iterrows():
            records.append(
                {
                    "art_code": str(row.get("公告编号", "")),
                    "title": str(row.get("公告标题", "")),
                    "notice_date": str(row.get("公告时间", "")),
                    "column_name": str(row.get("公告类型", "")),
                    "stock_code": stock_code,
                    "short_name": "",
                    "ann_type": "",
                    "source": "akshare",
                    "url": "",
                }
            )
        logger.info("[AKShare] 股票 %s 获取 %d 条公告", stock_code, len(records))
        return records

    except Exception as e:
        logger.warning("[AKShare] 失败: %s", e)
        return []


# ── 3级降级抓取主函数 ───────────────────────────────────────────────────────

def fetch_announcements(
    stock_code: str,
    begin_time: Optional[str] = None,
    end_time: Optional[str] = None,
    max_notices: int = 50,
) -> list[dict]:
    """
    3级降级抓取：CNINFO → EM → AKShare

    Args:
        stock_code: 股票代码，如 "002014"
        begin_time: 开始日期 "YYYY-MM-DD"（默认2020-01-01）
        end_time: 结束日期 "YYYY-MM-DD"（默认今天）
        max_notices: 最多返回条数

    Returns:
        合并去重的公告列表（按 notice_date 降序）
    """
    if not end_time:
        end_time = datetime.now().strftime("%Y-%m-%d")
    if not begin_time:
        begin_time = "2020-01-01"

    results: dict[str, dict] = {}  # art_code → parsed item

    # ── Level 1: 巨潮资讯（最准确）──
    try:
        cninfo_results = fetch_cninfo_announcements(
            stock_code=stock_code,
            begin_time=begin_time,
            end_time=end_time,
            page_size=30,
            max_pages=20,
        )
        for item in cninfo_results:
            if item["art_code"]:
                results[item["art_code"]] = item
        logger.info("[FETCHER] CNINFO 成功: %d 条", len(cninfo_results))
    except Exception as e:
        logger.warning("[FETCHER] CNINFO 降级: %s", e)

    # ── Level 2: 东方财富（补充近期数据）──
    if len(results) < max_notices:
        try:
            em_results = fetch_em_announcements(
                stock_code=stock_code,
                begin_time=begin_time,
                end_time=end_time,
                page_size=100,
                max_pages=20,
            )
            for item in em_results:
                if item["art_code"]:
                    results[item["art_code"]] = item
            logger.info("[FETCHER] EM 成功: %d 条", len(em_results))
        except Exception as e:
            logger.warning("[FETCHER] EM 降级: %s", e)

    # ── Level 3: AKShare ──
    if len(results) < max_notices:
        try:
            akshare_results = fetch_akshare_announcements(
                stock_code=stock_code,
                begin_time=begin_time.replace("-", ""),
                end_time=end_time.replace("-", ""),
            )
            for item in akshare_results:
                if item["art_code"]:
                    results[item["art_code"]] = item
            logger.info("[FETCHER] AKShare 成功: %d 条", len(akshare_results))
        except Exception as e:
            logger.warning("[FETCHER] AKShare 降级: %s", e)

    # 合并结果并按日期降序
    sorted_results = sorted(
        results.values(),
        key=lambda x: x.get("notice_date", ""),
        reverse=True,
    )

    return sorted_results[:max_notices]


# ── fetch_notice_detail: 获取单条公告详情 ───────────────────────────────────

_DETAIL_URL_CNINFO = "http://www.cninfo.com.cn/new/disclosure/detail"
_DETAIL_URL_EM = "https://data.eastmoney.com/notices/detail"


def fetch_notice_detail(art_code: str, stock_code: str, source: str = "cninfo") -> dict:
    """
    获取单条公告的详细信息（正文 URL、附件列表等）。

    Args:
        art_code: 公告ID（cninfo 的 announcementId 或 eastmoney 的 art_code）
        stock_code: 股票代码（用于构造 EM URL）
        source: 数据源，"cninfo" 或 "eastmoney"（默认 cninfo）

    Returns:
        dict: 包含 url, title, notice_date 等字段的详情字典
              如果获取失败返回带 error 字段的字典
    """
    if source == "cninfo":
        url = f"{_DETAIL_URL_CNINFO}?announcementId={art_code}"
        try:
            resp = requests.get(url, headers=HEADERS_CN, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            item = data.get("announcement", {})
            return {
                "success": True,
                "art_code": art_code,
                "source": "cninfo",
                "title": item.get("announcementTitle", ""),
                "notice_date": item.get("announcementTime", ""),
                "url": item.get("adjunctUrl", ""),
                "adjuncts": item.get("adjuncts", []),
                "body": data,
            }
        except Exception as e:
            logger.warning("[fetch_notice_detail] CNINFO 失败 art_code=%s: %s", art_code, e)
            return {"success": False, "art_code": art_code, "source": "cninfo", "error": str(e)}

    elif source == "eastmoney":
        url = f"{_DETAIL_URL_EM}/{stock_code}/{art_code}.html"
        try:
            resp = requests.get(url, headers=HEADERS_EM, timeout=15)
            resp.raise_for_status()
            return {
                "success": True,
                "art_code": art_code,
                "source": "eastmoney",
                "stock_code": stock_code,
                "url": url,
                "html_fetched": True,
                "note": "EM 详情需浏览器渲染，建议直接访问 URL",
            }
        except Exception as e:
            logger.warning("[fetch_notice_detail] EM 失败 art_code=%s: %s", art_code, e)
            return {"success": False, "art_code": art_code, "source": "eastmoney", "error": str(e)}

    else:
        return {"success": False, "art_code": art_code, "source": source, "error": "unknown source"}


if __name__ == "__main__":
    import pprint
    results = fetch_announcements("002014", max_notices=10)
    print(f"共获取 {len(results)} 条公告:")
    for r in results:
        print(f"  [{r['notice_date'][:10]}] [{r['column_name']}] {r['title'][:50]}")
