# -*- coding: utf-8 -*-
"""
图表3: 杜邦三因子贡献堆叠 - 堆叠面积图
====================================
数据来源: 模块2 financial_metrics.dupont_net_margin + dupont_asset_turnover + dupont_equity_multiplier
"""

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chart_factory import (
    ChartFactory, ChartConfig, StackedChart,
    setup_chinese_font, COLORS, init_chart_env
)


def create_dupont_stacked(
    years: List[int],
    dupont_net_margin: List[float],
    dupont_asset_turnover: List[float],
    dupont_equity_multiplier: List[float],
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建杜邦三因子贡献堆叠面积图
    
    Parameters
    ----------
    years : List[int]
        年份列表
    dupont_net_margin : List[float]
        杜邦-净利率列表
    dupont_asset_turnover : List[float]
        杜邦-资产周转率列表
    dupont_equity_multiplier : List[float]
        杜邦-权益乘数列表
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
        'y_series': [
            dupont_net_margin,
            dupont_asset_turnover,
            dupont_equity_multiplier
        ]
    }
    
    config = ChartConfig.get_chart_config('03_dupont_stacked')
    chart = ChartFactory.create('stacked_area', config)
    
    kwargs = {
        'xlabel': '年份',
        'ylabel': '杜邦分解因子',
        'title': '杜邦三因子贡献分解',
        'type': 'area',
        'colors': ['#3498DB', '#2ECC71', '#E74C3C'],
        'labels': ['净利率', '资产周转率', '权益乘数']
    }
    
    fig, ax = chart.create(data, **kwargs)
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart03_dupont_stacked.png')
        chart.save(filepath, dpi=150)
    
    return fig, ax


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    years = [2020, 2021, 2022, 2023, 2024]
    # 杜邦三因子（简化示例，数值不一定有实际意义）
    dupont_net_margin = [0.15, 0.16, 0.14, 0.15, 0.17]    # 净利率
    dupont_asset_turnover = [0.8, 0.85, 0.82, 0.88, 0.9]  # 资产周转率
    dupont_equity_multiplier = [2.0, 2.1, 2.0, 1.9, 1.8]  # 权益乘数
    
    return {
        'years': years,
        'dupont_net_margin': dupont_net_margin,
        'dupont_asset_turnover': dupont_asset_turnover,
        'dupont_equity_multiplier': dupont_equity_multiplier
    }


if __name__ == '__main__':
    init_chart_env()
    
    data = generate_sample_data()
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    
    fig, ax = create_dupont_stacked(
        data['years'],
        data['dupont_net_margin'],
        data['dupont_asset_turnover'],
        data['dupont_equity_multiplier'],
        output_dir=output_dir,
        stock_code='000001'
    )
    
    plt.show()
    print("✓ 图表3创建完成")