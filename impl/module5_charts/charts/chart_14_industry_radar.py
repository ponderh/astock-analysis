# -*- coding: utf-8 -*-
"""
图表14: 行业环境评估雷达
=========================
数据来源: 模块6 strategic_commitments 中的量化目标
类型: 雷达图
优先级: P1
输出: PNG 150dpi
"""

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from math import pi

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chart_factory import (
    ChartFactory, ChartConfig, 
    setup_chinese_font, COLORS, init_chart_env
)
from mda_loader import MDADataLoader


def create_industry_radar(
    strategic_commitments: List[Dict[str, str]],
    industry_scores: Dict[str, float] = None,
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建行业环境评估雷达图
    
    Parameters
    ----------
    strategic_commitments : List[Dict[str, str]]
        战略承诺列表，可用于提取量化目标
    industry_scores : Dict[str, float]
        行业评估得分，键为评估维度，值为0-100的得分
        包含: market_growth, competition_intensity, regulatory_risk, 
              technology_risk, supply_chain_risk
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
    
    # 默认评估维度
    default_categories = [
        '市场增长', '竞争强度', '监管风险', 
        '技术风险', '供应链风险'
    ]
    default_keys = [
        'market_growth', 'competition_intensity', 
        'regulatory_risk', 'technology_risk', 'supply_chain_risk'
    ]
    
    # 如果没有提供行业评分，从战略承诺中提取或使用默认值
    if industry_scores is None:
        industry_scores = extract_industry_scores_from_commitments(strategic_commitments)
    
    # 提取得分
    values = []
    for key in default_keys:
        score = industry_scores.get(key, 50)  # 默认50分
        values.append(score)
    
    # 确保有5个维度
    while len(values) < 5:
        values.append(50)
    values = values[:5]
    
    # 计算雷达图角度
    n_categories = len(default_categories)
    angles = [n / float(n_categories) * 2 * pi for n in range(n_categories)]
    angles += angles[:1]  # 闭合
    
    # 闭合数据
    values += values[:1]
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    
    # 绘制雷达图
    ax.plot(angles, values, 'o-', linewidth=2, color=COLORS['secondary'], markersize=8)
    ax.fill(angles, values, alpha=0.25, color=COLORS['secondary'])
    
    # 设置类别标签
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(default_categories, fontsize=12, fontweight='bold')
    
    # 设置径向刻度
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=9)
    
    # 添加网格线
    ax.grid(True, alpha=0.3)
    
    # 标题
    ax.set_title('行业环境评估雷达', fontsize=16, fontweight='bold', pad=20)
    
    # 添加得分标注
    for i, (angle, value) in enumerate(zip(angles[:-1], values[:-1])):
        ax.annotate(f'{int(value)}',
                    xy=(angle, value),
                    xytext=(10, 5),
                    textcoords='offset points',
                    fontsize=10,
                    fontweight='bold',
                    color=COLORS['primary'])
    
    plt.tight_layout()
    
    # 保存
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart14_industry_radar.png')
        fig.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"✓ 图表14已保存: {filepath}")
    
    return fig, ax


def extract_industry_scores_from_commitments(
    strategic_commitments: List[Dict[str, str]]
) -> Dict[str, float]:
    """
    从战略承诺中提取行业评估得分
    
    如果战略承诺中包含量化目标，可以尝试解析提取
    否则返回默认评分
    """
    if not strategic_commitments:
        # 返回默认评分（中等水平）
        return {
            'market_growth': 65,
            'competition_intensity': 70,
            'regulatory_risk': 45,
            'technology_risk': 55,
            'supply_chain_risk': 50
        }
    
    # 尝试从量化目标中提取评分
    # 这是一个简化实现，实际可能需要更复杂的NLP
    scores = {
        'market_growth': 60,
        'competition_intensity': 65,
        'regulatory_risk': 50,
        'technology_risk': 55,
        'supply_chain_risk': 45
    }
    
    # 基于承诺数量和关键词调整
    commitment_texts = ' '.join([
        c.get('commitment', '') + ' ' + c.get('quantitative_target', '')
        for c in strategic_commitments
    ])
    
    # 市场增长相关关键词
    if any(kw in commitment_texts for kw in ['增长', '拓展', '扩张', '海外', '全球']):
        scores['market_growth'] = min(90, scores['market_growth'] + 15)
    
    # 竞争相关
    if any(kw in commitment_texts for kw in ['竞争', '差异化', '品牌']):
        scores['competition_intensity'] = min(90, scores['competition_intensity'] + 10)
    
    # 监管风险（环保、合规相关承诺说明关注监管）
    if any(kw in commitment_texts for kw in ['环保', '合规', 'ESG', '碳排放']):
        scores['regulatory_risk'] = min(90, scores['regulatory_risk'] + 10)
    
    # 技术风险（研发、技术相关承诺说明关注技术）
    if any(kw in commitment_texts for kw in ['研发', '技术', '创新', '新材料']):
        scores['technology_risk'] = min(90, scores['technology_risk'] + 15)
    
    # 供应链风险（供应链、原料相关承诺说明关注供应链）
    if any(kw in commitment_texts for kw in ['供应链', '原料', '供应商', '多元化']):
        scores['supply_chain_risk'] = min(90, scores['supply_chain_risk'] + 10)
    
    return scores


def generate_sample_data() -> Dict[str, Any]:
    """生成示例数据用于测试"""
    strategic_commitments = [
        {
            'commitment': '持续加大研发投入，提升核心竞争力',
            'time_horizon': '2024-2026',
            'quantitative_target': '研发费用率提升至8%'
        },
        {
            'commitment': '深化数字化转型，打造智能制造体系',
            'time_horizon': '2024-2025',
            'quantitative_target': '生产效率提升30%'
        },
        {
            'commitment': '拓展海外市场，实现全球化布局',
            'time_horizon': '2024-2028',
            'quantitative_target': '海外营收占比达到40%'
        },
        {
            'commitment': '强化供应链韧性，保障原料稳定供应',
            'time_horizon': '2024-2025',
            'quantitative_target': '供应商多元化指数提升至0.8'
        },
        {
            'commitment': '践行ESG理念，推动可持续发展',
            'time_horizon': '2024-2030',
            'quantitative_target': '碳排放强度下降50%'
        }
    ]
    
    # 行业评估得分（示例）
    industry_scores = {
        'market_growth': 75,           # 市场增长潜力高
        'competition_intensity': 80,   # 竞争较激烈
        'regulatory_risk': 55,        # 监管风险中等
        'technology_risk': 70,        # 技术风险较高（需要持续研发）
        'supply_chain_risk': 45       # 供应链相对稳定
    }
    
    return {
        'strategic_commitments': strategic_commitments,
        'industry_scores': industry_scores
    }


def load_from_mda_json(file_path: str) -> Tuple[List[Dict], Dict[str, float]]:
    """从MD&A JSON文件加载数据"""
    if not os.path.exists(file_path):
        print(f"⚠ MD&A数据文件不存在: {file_path}，使用示例数据")
        data = generate_sample_data()
        return data['strategic_commitments'], data['industry_scores']
    
    loader = MD&ADataLoader()
    loader.load(file_path)
    
    commitments = loader.get_strategic_commitments()
    scores = extract_industry_scores_from_commitments(commitments)
    
    return commitments, scores


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='生成行业环境评估雷达图')
    parser.add_argument('--stock', type=str, default='000001', help='股票代码')
    parser.add_argument('--input', type=str, default=None, help='MD&A JSON文件路径')
    parser.add_argument('--output', type=str, default=None, help='输出目录')
    
    args = parser.parse_args()
    
    # 加载数据
    if args.input and os.path.exists(args.input):
        commitments, scores = load_from_mda_json(args.input)
    else:
        data = generate_sample_data()
        commitments = data['strategic_commitments']
        scores = data['industry_scores']
    
    # 输出目录
    output_dir = args.output or os.path.join(os.path.dirname(__file__), 'output')
    
    # 创建雷达图
    fig, ax = create_industry_radar(
        commitments,
        industry_scores=scores,
        output_dir=output_dir,
        stock_code=args.stock
    )
    
    plt.show()
    print("✓ 图表14创建完成")