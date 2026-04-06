# -*- coding: utf-8 -*-
"""
图表5: 资产负债率+有息负债率 - 双轴折线图
=======================================
数据来源: 模块2 financial_metrics.debt_ratio + interest_bearing_debt_ratio
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


def create_debt_ratios_trend(
    years: List[int],
    debt_ratio: List[float],
    interest_bearing_debt_ratio: List[float],
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建资产负债率+有息负债率双轴折线图
    
    Parameters
    ----------
    years : List[int]
        年份列表
    debt_ratio : List[float]
        资产负债率列表（%）
    interest_bearing_debt_ratio : List[float]
        有息负债率列表（%）
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
            ('资产负债率', debt_ratio)
        ],
        'y2_series': [
            ('有息负债率', interest_bearing_debt_ratio)
        ]
    }
    
    config = ChartConfig.get_chart_config('06_debt_ratios')
    chart = ChartFactory.create('dual_axis_line', config)
    
    kwargs = {
        'xlabel': '年份',
        'ylabel1': '资产负债率（%）',
        'ylabel2': '有息负债率（%）',
        'title': '资产负债率与有息负债率趋势',
        'colors': ['#3498DB'],
        'colors2': ['#E74C3C']
    }
    
    fig, ax = chart.create(data, **kwargs)
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart05_debt_ratios.png')
        chart.save(filepath, dpi=150)
    
    return fig, ax


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    years = [2020, 2021, 2022, 2023, 2024]
    debt_ratio = [45.2, 48.5, 50.1, 47.8, 46.3]
    interest_bearing_debt_ratio = [28.5, 30.2, 32.5, 29.8, 27.5]
    
    return {
        'years': years,
        'debt_ratio': debt_ratio,
        'interest_bearing_debt_ratio': interest_bearing_debt_ratio
    }


if __name__ == '__main__':
    init_chart_env()
    
    data = generate_sample_data()
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    
    fig, ax = create_debt_ratios_trend(
        data['years'],
        data['debt_ratio'],
        data['interest_bearing_debt_ratio'],
        output_dir=output_dir,
        stock_code='000001'
    )
    
    plt.show()
    print("✓ 图表5创建完成")