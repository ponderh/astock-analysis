# -*- coding: utf-8 -*-
"""
图表12: 管理层讨论要点词云
===========================
数据来源: 模块6 strategic_commitments + key_strategic_themes text字段
类型: 词云
优先级: P2
输出: PNG 150dpi
"""

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from wordcloud import WordCloud

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chart_factory import (
    ChartFactory, ChartConfig, 
    setup_chinese_font, COLORS, init_chart_env
)
from mda_loader import MDADataLoader


def create_strategy_wordcloud(
    strategic_commitments: List[Dict[str, str]],
    key_themes: List[Dict[str, str]],
    output_dir: str = None,
    stock_code: str = '000001'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    创建管理层讨论要点词云
    
    Parameters
    ----------
    strategic_commitments : List[Dict[str, str]]
        战略承诺列表，每项包含 commitment, time_horizon, quantitative_target
    key_themes : List[Dict[str, str]]
        关键战略主题列表，每项包含 theme, description
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
    
    # 合并所有文本用于词云
    text_segments = []
    
    # 添加战略承诺文本
    for item in strategic_commitments:
        if item.get('commitment'):
            text_segments.append(item['commitment'])
        if item.get('quantitative_target'):
            text_segments.append(item['quantitative_target'])
    
    # 添加关键主题文本
    for item in key_themes:
        if item.get('theme'):
            text_segments.append(item['theme'])
        if item.get('description'):
            text_segments.append(item['description'])
    
    # 合并为单一文本
    combined_text = ' '.join(text_segments)
    
    if not combined_text.strip():
        # 无数据时显示占位符
        combined_text = "暂无数据"
    
    # 获取中文字体路径
    font_path = get_chinese_font_path()
    
    # 创建词云
    wordcloud = WordCloud(
        font_path=font_path,
        width=1200,
        height=800,
        background_color='white',
        max_words=100,
        max_font_size=150,
        min_font_size=20,
        colormap='viridis',
        prefer_horizontal=0.7,
        scale=2
    ).generate(combined_text)
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(14, 9))
    
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis('off')
    ax.set_title('管理层讨论要点词云', fontsize=16, fontweight='bold', pad=20)
    
    plt.tight_layout()
    
    # 保存
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f'{stock_code}_chart12_strategy_wordcloud.png')
        fig.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"✓ 图表12已保存: {filepath}")
    
    return fig, ax


def get_chinese_font_path() -> Optional[str]:
    """获取可用的中文字体路径"""
    from matplotlib import font_manager
    
    # 字体fallback链
    font_names = [
        'SimHei',
        'Microsoft YaHei', 
        'PingFang SC',
        'Noto Sans CJK SC',
        'Noto Sans CJK',
        'WenQuanYi Micro Hei',
        'AR PL UMing CN'
    ]
    
    # 搜索系统字体
    font_paths = [
        '/usr/share/fonts',
        '/usr/local/share/fonts',
        os.path.expanduser('~/.fonts'),
        '/System/Library/Fonts',  # macOS
        'C:/Windows/Fonts'  # Windows
    ]
    
    for font_name in font_names:
        # 尝试通过字体名称查找
        try:
            font_list = font_manager.findfont(font_manager.FontProperties(family=font_name))
            if font_list and font_list != font_manager._load_default_font():
                return font_list
        except:
            pass
        
        # 尝试在系统字体目录中查找
        for font_dir in font_paths:
            if os.path.exists(font_dir):
                for root, dirs, files in os.walk(font_dir):
                    for f in files:
                        if f.endswith(('.ttf', '.otf')) and font_name.lower() in f.lower():
                            return os.path.join(root, f)
    
    # 返回None让WordCloud使用默认字体
    return None


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
    
    key_themes = [
        {
            'theme': '技术创新',
            'description': '聚焦新材料研发，构建技术壁垒，提升产品附加值'
        },
        {
            'theme': '数字化转型',
            'description': '推进智能制造，打造数字化供应链，提升运营效率'
        },
        {
            'theme': '国际化拓展',
            'description': '深耕东南亚市场，布局欧美高端客户，提升品牌影响力'
        },
        {
            'theme': '绿色发展',
            'description': '落实双碳目标，构建循环经济体系，实现低碳生产'
        },
        {
            'theme': '人才战略',
            'description': '强化人才梯队建设，完善激励机制，提升组织能力'
        }
    ]
    
    return {
        'strategic_commitments': strategic_commitments,
        'key_themes': key_themes
    }


def load_from_mda_json(file_path: str) -> Tuple[List[Dict], List[Dict]]:
    """从MD&A JSON文件加载数据"""
    if not os.path.exists(file_path):
        print(f"⚠ MD&A数据文件不存在: {file_path}，使用示例数据")
        data = generate_sample_data()
        return data['strategic_commitments'], data['key_themes']
    
    loader = MD&ADataLoader()
    loader.load(file_path)
    
    commitments = loader.get_strategic_commitments()
    themes = loader.get_key_strategic_themes()
    
    return commitments, themes


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='生成管理层讨论要点词云')
    parser.add_argument('--stock', type=str, default='000001', help='股票代码')
    parser.add_argument('--input', type=str, default=None, help='MD&A JSON文件路径')
    parser.add_argument('--output', type=str, default=None, help='输出目录')
    
    args = parser.parse_args()
    
    # 加载数据
    if args.input and os.path.exists(args.input):
        commitments, themes = load_from_mda_json(args.input)
    else:
        data = generate_sample_data()
        commitments = data['strategic_commitments']
        themes = data['key_themes']
    
    # 输出目录
    output_dir = args.output or os.path.join(os.path.dirname(__file__), 'output')
    
    # 创建词云
    fig, ax = create_strategy_wordcloud(
        commitments,
        themes,
        output_dir=output_dir,
        stock_code=args.stock
    )
    
    plt.show()
    print("✓ 图表12创建完成")