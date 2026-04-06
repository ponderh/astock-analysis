#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 3 图表生成测试脚本
测试图表7-11的生成时间和输出质量
"""

import os
import sys
import time
import traceback

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

# 导入图表模块
from charts.chart_07_pe_pb_ps import create_valuation_percentile, generate_sample_data as gen_data_07
from charts.chart_08_dcf_sensitivity import create_dcf_sensitivity, generate_sample_data as gen_data_08
from charts.chart_09_relative_valuation import create_relative_valuation, generate_sample_data as gen_data_09
from charts.chart_10_quarterly_revenue_profit import create_quarterly_revenue_profit, generate_sample_data as gen_data_10
from charts.chart_11_seasonality_heatmap import create_seasonality_heatmap, generate_sample_data as gen_data_11

from chart_factory import COLORS, init_chart_env

# 导入 matplotlib
import matplotlib.pyplot as plt


def test_chart_07(data, output_file, stock_code="000001"):
    """测试图表7：PE/PB/PS历史分位"""
    print(f"  调用参数: years={len(data['years'])}年, pe={len(data['pe'])}个数据点")
    fig, ax = create_valuation_percentile(
        years=data['years'],
        pe=data['pe'],
        pb=data['pb'],
        ps=data['ps'],
        output_dir=os.path.dirname(output_file),
        stock_code=stock_code
    )
    fig.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return fig, ax


def test_chart_08(data, output_file, stock_code="000001"):
    """测试图表8：DCF敏感性热力图"""
    print(f"  调用参数: wacc_range={data['wacc_range']}, base_value={data['base_value']}")
    fig, ax = create_dcf_sensitivity(
        wacc_range=data['wacc_range'],
        growth_range=data['growth_range'],
        base_value=data['base_value'],
        sensitivity_data=data['sensitivity_data'],
        output_dir=os.path.dirname(output_file),
        stock_code=stock_code
    )
    fig.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return fig, ax


def test_chart_09(data, output_file, stock_code="000001"):
    """测试图表9：相对估值横向比较"""
    print(f"  调用参数: company_pe={data['company_pe']}, company_pb={data['company_pb']}")
    fig, ax = create_relative_valuation(
        company_pe=data['company_pe'],
        company_pb=data['company_pb'],
        industry_avg_pe=data.get('industry_avg_pe'),
        industry_avg_pb=data.get('industry_avg_pb'),
        peer_data=data.get('peer_data'),
        output_dir=os.path.dirname(output_file),
        stock_code=stock_code
    )
    fig.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return fig, ax


def test_chart_10(data, output_file, stock_code="000001"):
    """测试图表10：季度营收/利润波动柱状图"""
    print(f"  调用参数: years={data['years']}, quarterly_revenue={len(data['quarterly_revenue'])}个季度")
    fig, ax = create_quarterly_revenue_profit(
        years=data['years'],
        quarterly_revenue=data['quarterly_revenue'],
        quarterly_profit=data['quarterly_profit'],
        output_dir=os.path.dirname(output_file),
        stock_code=stock_code
    )
    fig.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return fig, ax


def test_chart_11(data, output_file, stock_code="000001"):
    """测试图表11：季节性热力图"""
    print(f"  调用参数: years={data['years']}, quarterly_revenue={len(data['quarterly_revenue'])}个季度")
    fig, ax = create_seasonality_heatmap(
        years=data['years'],
        quarterly_revenue=data['quarterly_revenue'],
        quarterly_profit=data.get('quarterly_profit'),
        output_dir=os.path.dirname(output_file),
        stock_code=stock_code
    )
    fig.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return fig, ax


def main():
    """主测试函数"""
    print("="*60)
    print("Phase 3 图表生成性能测试")
    print("="*60)
    
    # 创建输出目录
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    # 测试配置
    stock_code = "000001"
    
    results = []
    total_start = time.time()
    
    # 测试图表7
    print(f"\n{'='*60}")
    print("测试 chart_07_valuation_percentile (PE/PB/PS历史分位)")
    print('='*60)
    try:
        init_chart_env()
        data = gen_data_07()
        output_file = os.path.join(output_dir, f"{stock_code}_chart07_test.png")
        start = time.time()
        test_chart_07(data, output_file, stock_code)
        elapsed = time.time() - start
        size = os.path.getsize(output_file)
        print(f"✓ 成功: 耗时 {elapsed:.2f}s, 大小 {size/1024:.1f}KB")
        results.append({'name': 'chart_07', 'success': True, 'elapsed': elapsed, 'size': size})
    except Exception as e:
        print(f"✗ 失败: {str(e)}")
        traceback.print_exc()
        results.append({'name': 'chart_07', 'success': False, 'error': str(e)})
    
    # 测试图表8
    print(f"\n{'='*60}")
    print("测试 chart_08_dcf_sensitivity (DCF敏感性热力图)")
    print('='*60)
    try:
        init_chart_env()
        data = gen_data_08()
        output_file = os.path.join(output_dir, f"{stock_code}_chart08_test.png")
        start = time.time()
        test_chart_08(data, output_file, stock_code)
        elapsed = time.time() - start
        size = os.path.getsize(output_file)
        print(f"✓ 成功: 耗时 {elapsed:.2f}s, 大小 {size/1024:.1f}KB")
        results.append({'name': 'chart_08', 'success': True, 'elapsed': elapsed, 'size': size})
    except Exception as e:
        print(f"✗ 失败: {str(e)}")
        traceback.print_exc()
        results.append({'name': 'chart_08', 'success': False, 'error': str(e)})
    
    # 测试图表9
    print(f"\n{'='*60}")
    print("测试 chart_09_relative_valuation (相对估值横向比较)")
    print('='*60)
    try:
        init_chart_env()
        data = gen_data_09()
        output_file = os.path.join(output_dir, f"{stock_code}_chart09_test.png")
        start = time.time()
        test_chart_09(data, output_file, stock_code)
        elapsed = time.time() - start
        size = os.path.getsize(output_file)
        print(f"✓ 成功: 耗时 {elapsed:.2f}s, 大小 {size/1024:.1f}KB")
        results.append({'name': 'chart_09', 'success': True, 'elapsed': elapsed, 'size': size})
    except Exception as e:
        print(f"✗ 失败: {str(e)}")
        traceback.print_exc()
        results.append({'name': 'chart_09', 'success': False, 'error': str(e)})
    
    # 测试图表10
    print(f"\n{'='*60}")
    print("测试 chart_10_quarterly_revenue_profit (季度营收/利润波动柱状图)")
    print('='*60)
    try:
        init_chart_env()
        data = gen_data_10()
        output_file = os.path.join(output_dir, f"{stock_code}_chart10_test.png")
        start = time.time()
        test_chart_10(data, output_file, stock_code)
        elapsed = time.time() - start
        size = os.path.getsize(output_file)
        print(f"✓ 成功: 耗时 {elapsed:.2f}s, 大小 {size/1024:.1f}KB")
        results.append({'name': 'chart_10', 'success': True, 'elapsed': elapsed, 'size': size})
    except Exception as e:
        print(f"✗ 失败: {str(e)}")
        traceback.print_exc()
        results.append({'name': 'chart_10', 'success': False, 'error': str(e)})
    
    # 测试图表11
    print(f"\n{'='*60}")
    print("测试 chart_11_seasonality_heatmap (季节性热力图)")
    print('='*60)
    try:
        init_chart_env()
        data = gen_data_11()
        output_file = os.path.join(output_dir, f"{stock_code}_chart11_test.png")
        start = time.time()
        test_chart_11(data, output_file, stock_code)
        elapsed = time.time() - start
        size = os.path.getsize(output_file)
        print(f"✓ 成功: 耗时 {elapsed:.2f}s, 大小 {size/1024:.1f}KB")
        results.append({'name': 'chart_11', 'success': True, 'elapsed': elapsed, 'size': size})
    except Exception as e:
        print(f"✗ 失败: {str(e)}")
        traceback.print_exc()
        results.append({'name': 'chart_11', 'success': False, 'error': str(e)})
    
    # 汇总结果
    total_elapsed = time.time() - total_start
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    success_count = sum(1 for r in results if r['success'])
    total_size = sum(r['size'] for r in results if r['success'])
    
    print(f"\n总计:")
    print(f"  - 成功: {success_count}/{len(results)}")
    print(f"  - 总耗时: {total_elapsed:.2f} 秒")
    print(f"  - 总文件大小: {total_size/1024:.1f} KB")
    
    print(f"\n详细结果:")
    for r in results:
        status = "✓" if r['success'] else "✗"
        if r['success']:
            print(f"  {status} {r['name']}: {r['elapsed']:.2f}s, {r['size']/1024:.1f}KB")
        else:
            print(f"  {status} {r['name']}: {r.get('error', 'Unknown error')}")
    
    # 性能评估
    print(f"\n性能评估:")
    max_time = 30  # 要求30秒内完成5张图表
    if total_elapsed <= max_time:
        print(f"  ✓ 总耗时 {total_elapsed:.2f}s < {max_time}s，符合性能要求")
    else:
        print(f"  ✗ 总耗时 {total_elapsed:.2f}s > {max_time}s，超出性能要求")
    
    for r in results:
        if r['success'] and r['elapsed'] > 10:
            print(f"  ⚠ {r['name']} 单张耗时 {r['elapsed']:.2f}s，建议优化")
    
    return results


if __name__ == "__main__":
    # 执行测试
    results = main()
    
    # 返回成功状态
    success = all(r['success'] for r in results)
    sys.exit(0 if success else 1)
