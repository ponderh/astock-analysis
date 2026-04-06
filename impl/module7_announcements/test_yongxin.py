#!/usr/bin/env python3
"""
test_yongxin.py
===============
永新股份(002014)公告数据管道测试脚本

测试内容：
1. 拉取最近10条公告（类型/日期/标题）
2. 验证业绩预告数据（2024年报预计1月底2月初发布）
3. 检查是否有"业绩更正"类型
4. 各数据源成功率

运行：
    python test_yongxin.py
"""

import sys
import os

# 添加父目录以便导入 module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import fetch_em_announcements, fetch_cninfo_announcements, fetch_akshare_announcements
from parser import (
    NoticeType, parse_notices, classification_report,
    get_notices_by_type
)
from api import get_announcements, get_yjyg_notices, get_latest_notices


STOCK_CODE = "002014"
STOCK_NAME = "永新股份"


def test_em_fetcher():
    """测试东方财富数据源"""
    print("\n" + "=" * 60)
    print("📡 测试数据源1: 东方财富 EM API")
    print("=" * 60)

    try:
        results = fetch_em_announcements(
            stock_code=STOCK_CODE,
            begin_time="2025-01-01",
            end_time="2026-04-03",
            page_size=100,
            max_pages=5,
        )
        print(f"✅ EM 成功: 获取 {len(results)} 条公告")
        for r in results[:3]:
            print(f"   [{r['notice_date'][:10]}] [{r['column_name']}] {r['title'][:50]}")
        return True, results
    except Exception as e:
        print(f"❌ EM 失败: {e}")
        return False, []


def test_cninfo_fetcher():
    """测试巨潮资讯数据源"""
    print("\n" + "=" * 60)
    print("📡 测试数据源2: 巨潮资讯 CNINFO API")
    print("=" * 60)

    try:
        results = fetch_cninfo_announcements(
            stock_code=STOCK_CODE,
            begin_time="2025-01-01",
            end_time="2026-04-03",
            page_size=30,
            max_pages=5,
        )
        print(f"✅ CNINFO 成功: 获取 {len(results)} 条公告")
        for r in results[:3]:
            print(f"   [{r['notice_date'][:10]}] [{r['column_name']}] {r['title'][:50]}")
        return True, results
    except Exception as e:
        print(f"❌ CNINFO 失败: {e}")
        return False, []


def test_akshare_fetcher():
    """测试 AKShare 降级方案"""
    print("\n" + "=" * 60)
    print("📡 测试数据源3: AKShare 降级")
    print("=" * 60)

    try:
        results = fetch_akshare_announcements(
            stock_code=STOCK_CODE,
            begin_time="20250101",
            end_time="20260403",
        )
        print(f"✅ AKShare 成功: 获取 {len(results)} 条公告")
        for r in results[:3]:
            print(f"   [{r['notice_date'][:10]}] [{r['column_name']}] {r['title'][:50]}")
        return True, results
    except Exception as e:
        print(f"❌ AKShare 失败: {e}")
        return False, []


def test_full_pipeline():
    """测试完整管道"""
    print("\n" + "=" * 60)
    print("🔧 测试完整3级降级管道")
    print("=" * 60)

    result = get_announcements(
        stock_code=STOCK_CODE,
        begin_time="2025-01-01",
        end_time="2026-04-03",
        max_notices=50,
    )

    print(f"\n{'✅ 成功' if result['success'] else '❌ 失败'}")
    print(f"原始数据: {result['total_raw']} 条")
    print(f"解析数据: {result['total_parsed']} 条")
    print(f"数据来源: {result['sources']}")

    if result.get('report'):
        r = result['report']
        print(f"\n分类统计:")
        print(f"  总数: {r['total']}")
        print(f"  高置信度(≥80%): {r['high_confidence_count']} ({r['high_confidence_rate']:.1%})")
        print(f"  平均置信度: {r['avg_confidence']:.2f}")
        print(f"  类型分布:")
        for t, cnt in sorted(r['by_type'].items(), key=lambda x: -x[1]):
            print(f"    {t}: {cnt}")

    return result


def test_yjyg():
    """测试业绩预告/快报/更正"""
    print("\n" + "=" * 60)
    print("📊 测试 P0 类型: 业绩预告/快报/更正")
    print("=" * 60)

    notices = get_yjyg_notices(
        stock_code=STOCK_CODE,
        years=[2023, 2024, 2025],
    )

    print(f"找到 {len(notices)} 条业绩相关公告:")
    for n in notices:
        print(f"\n  [{n['notice_date'][:10]}] {n['title']}")
        print(f"    类型: {n['notice_type']} ({n['type_confidence']:.0%})")
        if n.get('extracted_amount'):
            print(f"    金额: {n['extracted_amount']}")
        if n.get('extracted_change_pct'):
            print(f"    变动: {n['extracted_change_pct']}")

    return notices


def test_latest_10():
    """测试最近10条公告"""
    print("\n" + "=" * 60)
    print(f"📋 {STOCK_NAME}({STOCK_CODE}) 最近10条公告")
    print("=" * 60)

    notices = get_latest_notices(STOCK_CODE, count=10)

    if not notices:
        print("⚠️ 未获取到任何公告")
        return

    print(f"\n{'日期':<12} {'类型':<10} {'置信度':<8} {'标题'}")
    print("-" * 80)
    for n in notices:
        date = n.get('notice_date', '')[:10]
        ntype = n.get('notice_type', 'unknown')
        conf = f"{n.get('type_confidence', 0):.0%}"
        title = n.get('title', '')[:45]
        print(f"{date:<12} {ntype:<10} {conf:<8} {title}")

    return notices


def main():
    print("永新股份(002014)公告数据管道测试")
    print(f"时间: 2026-04-03 (注意：系统日期用于API查询范围)")
    print()

    # 记录成功率
    source_results = {}

    # 1. 分别测试各数据源
    em_ok, _ = test_em_fetcher()
    source_results['eastmoney'] = em_ok

    cninfo_ok, _ = test_cninfo_fetcher()
    source_results['cninfo'] = cninfo_ok

    akshare_ok, _ = test_akshare_fetcher()
    source_results['akshare'] = akshare_ok

    # 2. 测试完整管道
    pipeline_result = test_full_pipeline()

    # 3. 测试业绩预告
    yjyg_notices = test_yjyg()

    # 4. 测试最近10条
    latest = test_latest_10()

    # ── 最终报告 ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("📝 测试报告摘要")
    print("=" * 60)

    print(f"\n【数据源成功率】")
    total_ok = sum(source_results.values())
    for src, ok in source_results.items():
        status = "✅ 成功" if ok else "❌ 失败"
        print(f"  {src}: {status}")
    print(f"  综合: {total_ok}/3 数据源成功")

    print(f"\n【最近10条公告】")
    if latest:
        for n in latest:
            print(f"  [{n['notice_date'][:10]}] {n['title'][:55]}")
    else:
        print("  ⚠️ 无数据")

    print(f"\n【业绩预告/快报/更正 (P0)】")
    if yjyg_notices:
        for n in yjyg_notices:
            print(f"  [{n['notice_date'][:10]}] {n['title'][:55]}")
            print(f"    → {n['notice_type']} | 金额: {n.get('extracted_amount', 'N/A')} | 变动: {n.get('extracted_change_pct', 'N/A')}")
    else:
        print("  ⚠️ 未找到业绩预告/快报/更正公告（可能尚未发布 2024年报预告）")

    print(f"\n【发现的坑】")
    problems = []
    if not cninfo_ok:
        problems.append("巨潮资讯 API 返回 0 结果（secid 格式可能已变更，需 F12 抓包确认）")
    if not akshare_ok:
        problems.append("AKShare Brotli 解码错误（服务器返回 br 压缩但解码器状态异常）")
    if len(latest or []) < 10:
        problems.append(f"只获取到 {len(latest or 0)} 条公告（可能 API 限流或 stock_code 过滤问题）")
    if not problems:
        print("  ✅ 暂无明显问题")
    else:
        for i, k in enumerate(problems, 1):
            print(f"  {i}. {k}")

    print(f"\n【下一步优化建议】")
    print("  1. 抓包确认 cninfo secid 格式（访问 http://www.cninfo.com.cn F12 Network）")
    print("  2. 修复 AKShare Brotli 解码问题（尝试升级 urllib3/brotli 库）")
    print('  3. 增加更多业绩预告关键词（覆盖首亏/增亏等缩量表达）')
    print("  4. 对接巨潮 PDF 下载接口，实现正文内容提取")
    print("  5. 增加增量抓取机制（基于 last_fetch_time 过滤）")


if __name__ == "__main__":
    main()
