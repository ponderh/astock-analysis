# -*- coding: utf-8 -*-
"""
图表4: EPS + DPS + 累计分红 - 柱+线组合图
========================================
数据来源: 模块2 financial_metrics.eps + dps + cumulative_dps
"""

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chart_factory import (
    ChartFactory, ChartConfig, BarLineCombinationChart,
    setup_chinese_font, COLORS, init_chart_env
)


def create_eps_dps_combined(
    years: List[int],
    eps: List[float],
    dps: List[float],
    cumulative_dps: List[float],
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建EPS + DPS + 累计分红柱线组合图
    
    Parameters
    ----------
    years : List[int]
        年份列表
    eps : List[float]
        每股收益列表（元/股）
    dps : List[float]
        每股分红列表（元/股）
    cumulative_dps : List[float]
        累计分红列表（元/股）
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
        'bar_series': [
            ('每股收益(EPS)', eps),
            ('每股分红(DPS)', dps)
        ],
        'line_series': [
            ('累计分红', cumulative_dps)
        ]
    }
    
    config = ChartConfig.get_chart_config('04_eps_dps_combined')
    chart = ChartFactory.create('bar_line_combination', config)
    
    kwargs = {
        'xlabel': '年份',
        'ylabel1': '每股指标（元/股）',
        'ylabel2': '累计分红（元/股）',
        'title': '每股收益、每股分红与累计分红',
        'bar_colors': ['#3498DB', '#2ECC71'],
        'line_colors': ['#E74C3C']
    }
    
    fig, ax = chart.create(data, **kwargs)
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart04_eps_dps_combined.png')
        chart.save(filepath, dpi=150)
    
    return fig, ax


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    years = [2020, 2021, 2022, 2023, 2024]
    eps = [1.25, 1.48, 1.62, 1.85, 2.05]
    dps = [0.35, 0.42, 0.45, 0.52, 0.58]
    cumulative_dps = [0.35, 0.77, 1.22, 1.74, 2.32]
    
    return {
        'years': years,
        'eps': eps,
        'dps': dps,
        'cumulative_dps': cumulative_dps
    }


if __name__ == '__main__':
    init_chart_env()
    
    data = generate_sample_data()
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    
    fig, ax = create_eps_dps_combined(
        data['years'],
        data['eps'],
        data['dps'],
        data['cumulative_dps'],
        output_dir=output_dir,
        stock_code='000001'
    )
    
    plt.show()
    print("✓ 图表4创建完成")