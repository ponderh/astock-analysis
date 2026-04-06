# -*- coding: utf-8 -*-
"""
图表10: 季度营收/利润波动柱状图
===============================
数据来源: 模块2 quarterly_revenue + quarterly_profit
类型: 分组柱状图
优先级: P1
"""

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Any, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chart_factory import (
    ChartFactory, ChartConfig, 
    setup_chinese_font, COLORS, init_chart_env
)


def create_quarterly_revenue_profit(
    years: List[int],
    quarterly_revenue: List[float],
    quarterly_profit: List[float],
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建季度营收/利润波动柱状图
    
    Parameters
    ----------
    years : List[int]
        年份列表
    quarterly_revenue : List[float]
        季度营收数据（4*N长度，顺序：2020Q1,2020Q2,2020Q3,2020Q4,...）
    quarterly_profit : List[float]
        季度净利润数据（4*N长度）
    output_dir : str
        输出目录
    stock_code : str
        股票代码
        
    Returns
    -------
    Tuple[plt.Figure, plt.Axes]
        图表对象
    """
    # 初始化图表环境
    init_chart_env()
    
    n_years = len(years)
    n_quarters = 4
    
    # 准备x轴标签（按年份分组）
    quarter_labels = ['Q1', 'Q2', 'Q3', 'Q4']
    x_labels = []
    for year in years:
        for q in quarter_labels:
            x_labels.append(f'{year}\n{q}')
    
    # 计算每组柱状图的位置
    x = np.arange(len(x_labels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # 绘制营收柱状图（蓝色）
    bars1 = ax.bar(x - width/2, quarterly_revenue, width, 
                   label='营业收入', color=COLORS['series'][0], alpha=0.8)
    
    # 绘制净利润柱状图（红色，符合A股红涨习惯）
    bars2 = ax.bar(x + width/2, quarterly_profit, width, 
                   label='净利润', color=COLORS['series'][1], alpha=0.8)
    
    # 添加数值标签
    def add_labels(bars, values):
        for bar, val in zip(bars, values):
            if val and not np.isnan(val):
                height = bar.get_height()
                ax.annotate(f'{val:.1f}',
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3),
                            textcoords="offset points",
                            ha='center', va='bottom',
                            fontsize=7, rotation=45)
    
    add_labels(bars1, quarterly_revenue)
    add_labels(bars2, quarterly_profit)
    
    # 设置标签
    ax.set_xlabel('季度', fontsize=12)
    ax.set_ylabel('金额（亿元）', fontsize=12)
    ax.set_title('季度营收与净利润波动', fontsize=14, fontweight='bold')
    
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontsize=8)
    ax.legend(loc='upper left')
    
    # 网格
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    # 保存
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart10_quarterly_revenue_profit.png')
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        print(f"✓ 图表10已保存: {filepath}")
    
    return fig, ax


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    years = [2022, 2023, 2024]
    
    # 季度数据：4个季度 * 3年 = 12个季度
    quarterly_revenue = [
        # 2022
        25.3, 28.1, 26.5, 31.2,
        # 2023
        28.5, 32.1, 29.8, 35.6,
        # 2024
        31.2, 35.8, 33.5, 40.1
    ]
    
    quarterly_profit = [
        # 2022
        3.2, 3.8, 3.5, 4.2,
        # 2023
        3.8, 4.5, 4.1, 5.2,
        # 2024
        4.5, 5.3, 4.8, 6.1
    ]
    
    return {
        'years': years,
        'quarterly_revenue': quarterly_revenue,
        'quarterly_profit': quarterly_profit
    }


if __name__ == '__main__':
    # 示例数据
    data = generate_sample_data()
    
    # 创建图表
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    fig, ax = create_quarterly_revenue_profit(
        data['years'],
        data['quarterly_revenue'],
        data['quarterly_profit'],
        output_dir=output_dir,
        stock_code='000001'
    )
    
    plt.show()
    print("✓ 图表10创建完成")
