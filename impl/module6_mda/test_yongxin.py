#!/usr/bin/env python3
"""
module6_mda 测试脚本 - 永新股份(002014)原型验证
测试目标: 2020-2024年年报端到端成功率≥70%

运行方式:
    python test_yongxin.py
"""

import sys
import os
import json
import logging
from datetime import datetime

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import MDAPipeline
from models import PipelineStage


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # 抑制第三方库噪音
    for lib in ['urllib3', 'requests', 'PIL']:
        logging.getLogger(lib).setLevel(logging.WARNING)


def main():
    print("=" * 70)
    print("MD&A PDF解析管道 - 永新股份(002014)原型验证")
    print("=" * 70)

    setup_logging()

    # 初始化管道
    pipeline = MDAPipeline(
        stock_code="002014",
        org_id="gssz0002014"
    )

    # 测试年份
    test_years = [2020, 2021, 2022, 2023, 2024]

    print(f"\n测试范围: {test_years}")
    print(f"缓存目录: {pipeline.cache_dir}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 执行批量处理
    results = pipeline.process_batch(test_years)

    # 输出摘要
    summary = pipeline.summary(results)
    print(summary)

    # 保存详细结果到JSON
    output_file = pipeline.cache_dir / "test_results.json"
    results_dict = {}
    for year, result in results.items():
        r = {
            'stock_code': result.stock_code,
            'year': result.year,
            'end_to_end_success': result.end_to_end_success,
            'quality_grade': result.quality_score.grade if result.quality_score else None,
            'quality_score': result.quality_score.overall_score if result.quality_score else None,
            'mda_char_count': result.mda_section.char_count if result.mda_section else None,
            'stages': {
                'download': {
                    'success': result.download_result.success if result.download_result else False,
                    'method': result.download_result.method if result.download_result else None,
                    'error': result.download_result.error if result.download_result else None
                },
                'extract': {
                    'success': result.extract_result.success if result.extract_result else False,
                    'method': result.extract_result.method if result.extract_result else None,
                    'error': result.extract_result.error if result.extract_result else None
                },
                'locate': {
                    'success': result.locate_result.success if result.locate_result else False,
                    'method': result.locate_result.method if result.locate_result else None,
                    'confidence': result.locate_result.metadata.get('confidence', 0) if result.locate_result else 0
                },
                'analyze': {
                    'success': result.analyze_result.success if result.analyze_result else False,
                    'method': result.analyze_result.method if result.analyze_result else None,
                    'hallucination_flags': result.analyze_result.metadata.get('hallucination_flags', []) if result.analyze_result and result.analyze_result.metadata else []
                }
            },
            'strategic_data_keys': list(result.strategic_analysis.structured_data.keys()) if result.strategic_analysis and result.strategic_analysis.structured_data else []
        }
        results_dict[year] = r

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_dict, f, ensure_ascii=False, indent=2)

    print(f"\n详细结果已保存: {output_file}")

    # 统计端到端成功率
    total = len(results)
    success_count = sum(1 for r in results.values() if r.end_to_end_success)
    success_rate = success_count / total if total > 0 else 0

    print(f"\n{'='*70}")
    print(f"端到端成功率: {success_count}/{total} = {success_rate:.1%}")
    print(f"目标: ≥70%")
    if success_rate >= 0.70:
        print("✅ 原型验证通过!")
    else:
        print(f"❌ 原型验证未通过 (差距: {(0.70 - success_rate):.1%})")
    print(f"{'='*70}")

    # 逐阶段统计
    stage_stats = {}
    for stage in ['download', 'extract', 'locate', 'analyze']:
        stage_results = []
        for year, result in results.items():
            stage_result = getattr(result, f'{stage}_result', None)
            if stage_result:
                stage_results.append((year, stage_result.success, stage_result.method or stage_result.error))
        stage_stats[stage] = stage_results

    print(f"\n分阶段详情:")
    for stage, stage_results in stage_stats.items():
        ok_count = sum(1 for _, ok, _ in stage_results if ok)
        print(f"  {stage}: {ok_count}/{len(stage_results)}")
        for year, ok, method_or_err in stage_results:
            icon = "✅" if ok else "❌"
            print(f"    {icon} {year}: {method_or_err}")

    return 0 if success_rate >= 0.70 else 1


if __name__ == '__main__':
    sys.exit(main())
