# -*- coding: utf-8 -*-
"""
图表8: DCF敏感性热力图
=======================
数据来源: DCF参数敏感性分析（WACC x 永续增长率）
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


def create_dcf_sensitivity(
    wacc_range: List[float] = None,
    growth_range: List[float] = None,
    base_value: float = 100.0,
    sensitivity_data: List[List[float]] = None,
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建DCF敏感性热力图
    
    Parameters
    ----------
    wacc_range : List[float]
        WACC范围（百分比），如 [8, 9, 10, 11, 12]
    growth_range : List[float]
        永续增长率范围（百分比），如 [1, 2, 3, 4, 5]
    base_value : float
        基准股价/估值
    sensitivity_data : List[List[float]]
        预计算的敏感性矩阵数据，若提供则直接使用
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
    
    # 默认参数范围
    if wacc_range is None:
        wacc_range = [6, 7, 8, 9, 10, 11, 12]
    if growth_range is None:
        growth_range = [1, 2, 3, 4, 5]
    
    # 计算敏感性矩阵
    if sensitivity_data is None:
        sensitivity_matrix = calculate_dcf_sensitivity(
            base_value, wacc_range, growth_range
        )
    else:
        sensitivity_matrix = sensitivity_data
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # 使用红黄绿反转色图（高值绿，低值红 - 符合A股习惯）
    cmap = 'RdYlGn_r'
    
    # 绘制热力图
    sns.heatmap(
        sensitivity_matrix,
        xticklabels=[f'{g:.1f}%' for g in growth_range],
        yticklabels=[f'{w:.1f}%' for w in wacc_range],
        cmap=cmap,
        annot=True,
        fmt='.1f',
        ax=ax,
        cbar_kws={'label': 'DCF估值（元）'},
        linewidths=0.5,
        linecolor='white'
    )
    
    # 设置标签
    ax.set_xlabel('永续增长率（%）', fontsize=12)
    ax.set_ylabel('WACC（%）', fontsize=12)
    ax.set_title('DCF 敏感性分析热力图', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    # 保存
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart08_dcf_sensitivity.png')
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        print(f"✓ 图表8已保存: {filepath}")
    
    return fig, ax


def calculate_dcf_sensitivity(
    base_value: float,
    wacc_range: List[float],
    growth_range: List[float]
) -> List[List[float]]:
    """
    计算DCF敏感性矩阵
    
    使用简化的DCF公式: V = FCF * (1+g) / (WACC - g)
    
    Parameters
    ----------
    base_value : float
        基准估值
    wacc_range : List[float]
        WACC范围
    growth_range : List[float]
        永续增长率范围
        
    Returns
    -------
    List[List[float]]
        敏感性矩阵
    """
    matrix = []
    
    for wacc in wacc_range:
        row = []
        for growth in growth_range:
            # 简化DCF计算
            wacc_decimal = wacc / 100
            growth_decimal = growth / 100
            
            if wacc_decimal <= growth_decimal:
                # 无效区域
                value = np.nan
            else:
                # 简化计算：假设DCF值与 (WACC - growth) 成反比
                # 调整系数使结果在合理范围
                ratio = (wacc_decimal - growth_decimal) / wacc_decimal
                value = base_value * (1 + 0.1 / ratio)
            
            row.append(value)
        matrix.append(row)
    
    return matrix


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    wacc_range = [6, 7, 8, 9, 10, 11, 12]
    growth_range = [1, 2, 3, 4, 5]
    
    # 计算敏感性矩阵
    sensitivity_data = calculate_dcf_sensitivity(100.0, wacc_range, growth_range)
    
    return {
        'wacc_range': wacc_range,
        'growth_range': growth_range,
        'base_value': 100.0,
        'sensitivity_data': sensitivity_data
    }


if __name__ == '__main__':
    # 示例数据
    data = generate_sample_data()
    
    # 创建图表
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    fig, ax = create_dcf_sensitivity(
        wacc_range=data['wacc_range'],
        growth_range=data['growth_range'],
        base_value=data['base_value'],
        sensitivity_data=data['sensitivity_data'],
        output_dir=output_dir,
        stock_code='000001'
    )
    
    plt.show()
    print("✓ 图表8创建完成")
