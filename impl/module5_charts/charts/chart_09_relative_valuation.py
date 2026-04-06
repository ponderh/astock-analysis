# -*- coding: utf-8 -*-
"""
图表9: 相对估值横向比较 - 柱状图
=================================
数据来源: 与行业平均PE/PB对比
类型: 柱状图
优先级: P2
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


def create_relative_valuation(
    company_pe: float,
    company_pb: float,
    industry_avg_pe: float = None,
    industry_avg_pb: float = None,
    peer_data: List[Dict[str, Any]] = None,
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建相对估值横向比较柱状图
    
    Parameters
    ----------
    company_pe : float
        公司PE
    company_pb : float
        公司PB
    industry_avg_pe : float
        行业平均PE
    industry_avg_pb : float
        行业平均PB
    peer_data : List[Dict]
        同业公司数据列表，格式: [{'name': '公司A', 'pe': 12.5, 'pb': 1.8}, ...]
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
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # 准备数据
    labels = []
    pe_values = []
    pb_values = []
    
    # 添加目标公司
    labels.append(f'{stock_code}\n(本公司)')
    pe_values.append(company_pe)
    pb_values.append(company_pb)
    
    # 添加行业平均
    if industry_avg_pe is not None:
        labels.append('行业平均')
        pe_values.append(industry_avg_pe)
        pb_values.append(industry_avg_pb if industry_avg_pb else 1.0)
    
    # 添加同业公司数据
    if peer_data:
        for peer in peer_data:
            labels.append(peer.get('name', '同业公司'))
            pe_values.append(peer.get('pe', 10.0))
            pb_values.append(peer.get('pb', 1.0))
    
    x = np.arange(len(labels))
    width = 0.35
    
    # 绘制PE柱状图
    bars1 = ax.bar(x - width/2, pe_values, width, label='PE', color=COLORS['series'][0], alpha=0.8)
    
    # 绘制PB柱状图
    bars2 = ax.bar(x + width/2, pb_values, width, label='PB', color=COLORS['series'][1], alpha=0.8)
    
    # 添加数值标签
    for bar in bars1:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=9)
    
    for bar in bars2:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=9)
    
    # 设置标签
    ax.set_xlabel('对比公司', fontsize=12)
    ax.set_ylabel('估值指标', fontsize=12)
    ax.set_title('相对估值横向对比', fontsize=14, fontweight='bold')
    
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.legend(loc='upper right')
    
    # 网格
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    # 保存
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart09_relative_valuation.png')
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        print(f"✓ 图表9已保存: {filepath}")
    
    return fig, ax


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    return {
        'company_pe': 14.5,
        'company_pb': 2.1,
        'industry_avg_pe': 16.8,
        'industry_avg_pb': 2.5,
        'peer_data': [
            {'name': '同业A', 'pe': 12.3, 'pb': 1.8},
            {'name': '同业B', 'pe': 18.5, 'pb': 2.9},
            {'name': '同业C', 'pe': 15.2, 'pb': 2.2},
            {'name': '同业D', 'pe': 11.8, 'pb': 1.5},
        ]
    }


if __name__ == '__main__':
    # 示例数据
    data = generate_sample_data()
    
    # 创建图表
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    fig, ax = create_relative_valuation(
        company_pe=data['company_pe'],
        company_pb=data['company_pb'],
        industry_avg_pe=data['industry_avg_pe'],
        industry_avg_pb=data['industry_avg_pb'],
        peer_data=data['peer_data'],
        output_dir=output_dir,
        stock_code='000001'
    )
    
    plt.show()
    print("✓ 图表9创建完成")
