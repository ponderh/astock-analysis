# -*- coding: utf-8 -*-
"""
图表1: 营收/净利润趋势 - 双轴折线图
=================================
数据来源: 模块2 financial_metrics.revenue + net_profit
"""

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Any, Tuple

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chart_factory import (
    ChartFactory, ChartConfig, DualAxisLineChart, 
    setup_chinese_font, COLORS, init_chart_env
)


def create_revenue_profit_trend(
    years: List[int],
    revenue: List[float],
    net_profit: List[float],
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建营收/净利润趋势双轴折线图
    
    Parameters
    ----------
    years : List[int]
        年份列表
    revenue : List[float]
        营业收入列表（亿元）
    net_profit : List[float]
        净利润列表（亿元）
    output_dir : str
        输出目录
    stock_code : str
        股票代码
        
    Returns
    -------
    Tuple[plt.Figure, plt.Axes]
        图表对象
    """
    # 准备数据
    data = {
        'years': years,
        'y1_series': [
            ('营业收入', revenue)
        ],
        'y2_series': [
            ('净利润', net_profit)
        ]
    }
    
    # 获取配置
    config = ChartConfig.get_chart_config('01_revenue_profit_trend')
    
    # 创建双轴折线图
    chart = ChartFactory.create('dual_axis_line', config)
    
    kwargs = {
        'xlabel': '年份',
        'ylabel1': '营业收入（亿元）',
        'ylabel2': '净利润（亿元）',
        'title': '营业收入与净利润趋势',
        'colors': ['#3498DB'],
        'colors2': ['#E74C3C']
    }
    
    fig, ax = chart.create(data, **kwargs)
    
    # 保存
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart01_revenue_profit_trend.png')
        chart.save(filepath, dpi=150)
    
    return fig, ax


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    years = [2020, 2021, 2022, 2023, 2024]
    revenue = [100.5, 120.3, 135.8, 150.2, 168.9]
    net_profit = [15.2, 18.5, 20.1, 22.8, 25.6]
    
    return {
        'years': years,
        'revenue': revenue,
        'net_profit': net_profit
    }


if __name__ == '__main__':
    # 初始化环境
    init_chart_env()
    
    # 示例数据
    data = generate_sample_data()
    
    # 创建图表
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    fig, ax = create_revenue_profit_trend(
        data['years'],
        data['revenue'],
        data['net_profit'],
        output_dir=output_dir,
        stock_code='000001'
    )
    
    plt.show()
    print("✓ 图表1创建完成")