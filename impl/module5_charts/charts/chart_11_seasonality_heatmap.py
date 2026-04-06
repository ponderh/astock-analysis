# -*- coding: utf-8 -*-
"""
图表11: 季节性热力图（环比+同比）
=================================
数据来源: 季度数据矩阵（年份×季度）
类型: 热力图
优先级: P1
"""

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from typing import Dict, List, Any, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chart_factory import (
    ChartFactory, ChartConfig, 
    setup_chinese_font, COLORS, init_chart_env
)


def create_seasonality_heatmap(
    years: List[int],
    quarterly_revenue: List[float],
    quarterly_profit: List[float] = None,
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建季节性热力图（环比+同比）
    
    Parameters
    ----------
    years : List[int]
        年份列表
    quarterly_revenue : List[float]
        季度营收数据（4*N长度）
    quarterly_profit : List[float]
        季度净利润数据（4*N长度，可选）
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
    quarters = ['Q1', 'Q2', 'Q3', 'Q4']
    
    # 重组数据为矩阵（年份×季度）
    revenue_matrix = np.zeros((n_years, 4))
    for i, year in enumerate(years):
        for j in range(4):
            idx = i * 4 + j
            if idx < len(quarterly_revenue):
                revenue_matrix[i, j] = quarterly_revenue[idx]
    
    # 计算同比增长率矩阵
    yoy_matrix = np.zeros((n_years, 4))
    for i in range(n_years):
        for j in range(4):
            if i == 0:
                yoy_matrix[i, j] = 0  # 首年无同比数据
            else:
                prev_val = revenue_matrix[i-1, j]
                curr_val = revenue_matrix[i, j]
                if prev_val > 0:
                    yoy_matrix[i, j] = ((curr_val - prev_val) / prev_val) * 100
    
    # 计算环比增长率矩阵
    qoq_matrix = np.zeros((n_years, 4))
    for i in range(n_years):
        for j in range(4):
            if j == 0:
                if i == 0:
                    qoq_matrix[i, j] = 0  # 首年首季无环比
                else:
                    # 与上年Q4比较
                    prev_val = revenue_matrix[i-1, 3]
                    curr_val = revenue_matrix[i, j]
                    if prev_val > 0:
                        qoq_matrix[i, j] = ((curr_val - prev_val) / prev_val) * 100
            else:
                prev_val = revenue_matrix[i, j-1]
                curr_val = revenue_matrix[i, j]
                if prev_val > 0:
                    qoq_matrix[i, j] = ((curr_val - prev_val) / prev_val) * 100
    
    # 创建双热力图
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    
    # 左图：同比增长率
    ax1 = axes[0]
    sns.heatmap(
        yoy_matrix,
        xticklabels=quarters,
        yticklabels=[str(y) for y in years],
        cmap='RdBu_r',  # 红蓝色图：正（红）负（蓝）
        annot=True,
        fmt='.1f',
        ax=ax1,
        cbar_kws={'label': '同比增长率（%）'},
        linewidths=0.5,
        center=0,
        vmin=-30,
        vmax=30
    )
    ax1.set_title('同比增长率（%）', fontsize=14, fontweight='bold')
    ax1.set_xlabel('季度', fontsize=12)
    ax1.set_ylabel('年份', fontsize=12)
    
    # 右图：环比增长率
    ax2 = axes[1]
    sns.heatmap(
        qoq_matrix,
        xticklabels=quarters,
        yticklabels=[str(y) for y in years],
        cmap='RdBu_r',
        annot=True,
        fmt='.1f',
        ax=ax2,
        cbar_kws={'label': '环比增长率（%）'},
        linewidths=0.5,
        center=0,
        vmin=-30,
        vmax=30
    )
    ax2.set_title('环比增长率（%）', fontsize=14, fontweight='bold')
    ax2.set_xlabel('季度', fontsize=12)
    ax2.set_ylabel('年份', fontsize=12)
    
    # 总标题
    fig.suptitle('季节性波动热力图（同比+环比）', fontsize=16, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    
    # 保存
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart11_seasonality_heatmap.png')
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        print(f"✓ 图表11已保存: {filepath}")
    
    return fig, axes


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    years = [2022, 2023, 2024]
    
    # 季度营收数据
    quarterly_revenue = [
        # 2022
        25.3, 28.1, 26.5, 31.2,
        # 2023
        28.5, 32.1, 29.8, 35.6,
        # 2024
        31.2, 35.8, 33.5, 40.1
    ]
    
    return {
        'years': years,
        'quarterly_revenue': quarterly_revenue
    }


if __name__ == '__main__':
    # 示例数据
    data = generate_sample_data()
    
    # 创建图表
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    fig, ax = create_seasonality_heatmap(
        data['years'],
        data['quarterly_revenue'],
        output_dir=output_dir,
        stock_code='000001'
    )
    
    plt.show()
    print("✓ 图表11创建完成")
