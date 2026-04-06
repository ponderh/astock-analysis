# -*- coding: utf-8 -*-
"""
图表15: 核心指标仪表盘 - 组合仪表盘
=================================
数据来源: 模块2 综合指标
"""

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chart_factory import (
    ChartFactory, ChartConfig, DashboardChart,
    setup_chinese_font, COLORS, init_chart_env
)


def create_dashboard(
    metrics: Dict[str, Any],
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建核心指标仪表盘
    
    Parameters
    ----------
    metrics : Dict[str, Any]
        核心指标字典，示例:
        {
            'ROE': '15.2%',
            '毛利率': '32.5%',
            '净利率': '18.7%',
            'ROIC': '12.3%',
            '资产负债率': '45.2%',
            '股息率': '2.8%'
        }
    output_dir : str
        输出目录
    stock_code : str
        股票代码
        
    Returns
    -------
    Tuple[plt.Figure, plt.Axes]
        图表对象
    """
    # 2x3 布局的仪表盘
    layout = {'rows': 2, 'cols': 3}
    
    data = {
        'metrics': metrics
    }
    
    config = ChartConfig.get_chart_config('15_dashboard')
    chart = ChartFactory.create('dashboard', config)
    
    kwargs = {
        'title': '核心财务指标仪表盘',
        'layout': layout
    }
    
    fig, ax = chart.create(data, **kwargs)
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart15_dashboard.png')
        chart.save(filepath, dpi=150)
    
    return fig, ax


import matplotlib.font_manager as fm

# 扩展字体fallback链（包含更多中文字体）
EXTENDED_FONT_CHAIN = [
    'SimHei',
    'Microsoft YaHei', 
    'PingFang SC',
    'Noto Sans CJK SC',
    'WenQuanYi Micro Hei',
    'Arial'
]


def setup_chinese_font_extended():
    """设置中文字体（扩展6级fallback）"""
    available_fonts = [f.name for f in fm.fontManager.ttflist]
    
    for font in EXTENDED_FONT_CHAIN:
        if font in available_fonts:
            plt.rcParams['font.sans-serif'] = [font]
            plt.rcParams['axes.unicode_minus'] = False
            print(f"✓ 使用字体: {font}")
            return True
    
    print("⚠ 警告: 未找到中文字体，中文可能显示为方块")
    return False


def create_advanced_dashboard(
    metrics: Dict[str, Any],
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, List[plt.Axes]]:
    """
    创建高级仪表盘（含迷你图表）
    
    Parameters
    ----------
    metrics : Dict[str, Any]
        核心指标字典
    output_dir : str
        输出目录
    stock_code : str
        股票代码
        
    Returns
    -------
    Tuple[plt.Figure, List[plt.Axes]]
        图表对象
    """
    # 初始化图表环境（设置扩展中文字体fallback链）
    setup_chinese_font_extended()
    
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(f'{stock_code} 核心财务指标仪表盘', fontsize=16, fontweight='bold')
    
    # 定义仪表盘布局：指标名称、当前值、颜色指示
    dashboard_items = [
        ('ROE', '15.2%', '#3498DB', 'up'),
        ('毛利率', '32.5%', '#2ECC71', 'up'),
        ('净利率', '18.7%', '#3498DB', 'up'),
        ('ROIC', '12.3%', '#E74C3C', 'up'),
        ('资产负债率', '45.2%', '#F39C12', 'down'),
        ('股息率', '2.8%', '#9B59B6', 'up'),
    ]
    
    for idx, (name, value, color, trend) in enumerate(dashboard_items):
        ax = axes.flatten()[idx]
        ax.set_axis_off()
        
        # 绘制卡片背景
        rect = plt.Rectangle((0.05, 0.1), 0.9, 0.85, fill=True, 
                             facecolor='white', edgecolor=color, linewidth=2,
                             transform=ax.transAxes)
        ax.add_patch(rect)
        
        # 指标名称
        ax.text(0.5, 0.75, name, ha='center', va='center', fontsize=12,
               transform=ax.transAxes, fontweight='bold')
        
        # 指标值
        ax.text(0.5, 0.45, value, ha='center', va='center', fontsize=20,
               transform=ax.transAxes, fontweight='bold', color=color)
        
        # 趋势指示
        trend_arrow = '↑' if trend == 'up' else '↓'
        trend_color = COLORS['bullish'] if trend == 'up' else COLORS['bearish']
        ax.text(0.5, 0.2, trend_arrow, ha='center', va='center', fontsize=14,
               transform=ax.transAxes, color=trend_color)
    
    plt.tight_layout()
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart15_dashboard.png')
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        print(f"✓ 仪表盘已保存: {filepath}")
    
    return fig, axes.flatten()


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    return {
        'ROE': '15.2%',
        '毛利率': '32.5%',
        '净利率': '18.7%',
        'ROIC': '12.3%',
        '资产负债率': '45.2%',
        '股息率': '2.8%'
    }


if __name__ == '__main__':
    init_chart_env()
    
    data = generate_sample_data()
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    
    fig, axes = create_advanced_dashboard(
        data,
        output_dir=output_dir,
        stock_code='000001'
    )
    
    plt.show()
    print("✓ 图表15创建完成")