# -*- coding: utf-8 -*-
"""
图表2: ROIC vs WACC趋势 - 双轴折线图
===================================
数据来源: 模块2 financial_metrics.roic + wacc
"""

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chart_factory import (
    ChartFactory, ChartConfig, DualAxisLineChart, 
    setup_chinese_font, COLORS, init_chart_env
)


def create_roic_wacc_trend(
    years: List[int],
    roic: List[float],
    wacc: List[float],
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建ROIC vs WACC趋势双轴折线图
    
    Parameters
    ----------
    years : List[int]
        年份列表
    roic : List[float]
        ROIC列表（%）
    wacc : List[float]
        WACC列表（%）
    output_dir : str
        输出目录
    stock_code : str
        股票代码
        
    Returns
    -------
    Tuple[plt.Figure, plt.Axes]
        图表对象
    """
    data = {
        'years': years,
        'y1_series': [
            ('ROIC', roic)
        ],
        'y2_series': [
            ('WACC', wacc)
        ]
    }
    
    config = ChartConfig.get_chart_config('02_roic_wacc_trend')
    chart = ChartFactory.create('dual_axis_line', config)
    
    kwargs = {
        'xlabel': '年份',
        'ylabel1': 'ROIC（%）',
        'ylabel2': 'WACC（%）',
        'title': 'ROIC 与 WACC 趋势对比',
        'colors': ['#3498DB'],
        'colors2': ['#E67E22']
    }
    
    fig, ax = chart.create(data, **kwargs)
    
    # 添加盈亏平衡线（ROIC = WACC）
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    ax.text(years[0], 0.5, '盈亏平衡线', fontsize=9, color='gray')
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart02_roic_wacc_trend.png')
        chart.save(filepath, dpi=150)
    
    return fig, ax


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    years = [2020, 2021, 2022, 2023, 2024]
    roic = [8.5, 9.2, 7.8, 10.1, 11.3]
    wacc = [8.5, 8.5, 8.5, 8.5, 8.5]
    
    return {
        'years': years,
        'roic': roic,
        'wacc': wacc
    }


if __name__ == '__main__':
    init_chart_env()
    
    data = generate_sample_data()
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    
    fig, ax = create_roic_wacc_trend(
        data['years'],
        data['roic'],
        data['wacc'],
        output_dir=output_dir,
        stock_code='000001'
    )
    
    plt.show()
    print("✓ 图表2创建完成")