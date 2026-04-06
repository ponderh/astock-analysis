# -*- coding: utf-8 -*-
"""
ChartFactory - 图表工厂基类
===========================
工厂模式实现：支持 LineChart / BarChart / StackedChart / RadarChart / Heatmap / Dashboard
中文字体4级fallback链（定义在 chart_config.yaml）
"""

import os
import yaml
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from typing import Dict, List, Any, Optional, Tuple
from abc import ABC, abstractmethod
import numpy as np


# 字体fallback链（来自 chart_config.yaml）
# 覆盖 Windows(SimHei) + macOS(PingFang) + Linux(Noto Sans CJK)
FONT_FALLBACK_CHAIN = [
    'SimHei',
    'Microsoft YaHei',
    'PingFang SC',
    'Noto Sans CJK SC',
    'Noto Sans CJK',
    'Arial'
]

# A股配色方案（红涨绿跌）
COLORS = {
    'bullish': '#E74C3C',      # 红色 - 上涨/正增长
    'bearish': '#27AE60',      # 绿色 - 下跌/负增长
    'primary': '#2C3E50',      # 深蓝灰
    'secondary': '#3498DB',    # 蓝色
    'accent': '#E67E22',       # 橙色
    'series': [
        '#3498DB', '#E74C3C', '#2ECC71', '#F39C12',
        '#9B59B6', '#1ABC9C', '#34495E', '#E67E22'
    ]
}


class ChartConfig:
    """图表配置加载器"""
    
    _config = None
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> Dict:
        """加载chart_config.yaml"""
        if cls._config is not None:
            return cls._config
            
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), 'chart_config.yaml')
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                cls._config = yaml.safe_load(f)
        else:
            # 使用默认配置
            cls._config = cls._get_default_config()
        
        return cls._config
    
    @classmethod
    def _get_default_config(cls) -> Dict:
        """获取默认配置"""
        return {
            'global': {
                'font_fallback': FONT_FALLBACK_CHAIN,
                'figure_size': {'width': 12, 'height': 8},
                'dpi': 150,
                'style': 'seaborn-v0_8-whitegrid'
            },
            'colors': COLORS
        }
    
    @classmethod
    def get_chart_config(cls, chart_id: str) -> Dict:
        """获取单个图表配置"""
        config = cls.load()
        return config.get(f'chart_{chart_id}', {})


def setup_chinese_font():
    """设置中文字体（4级fallback）"""
    for font in FONT_FALLBACK_CHAIN:
        try:
            # 检查字体是否可用
            available_fonts = [f.name for f in fm.fontManager.ttflist]
            if font in available_fonts:
                plt.rcParams['font.sans-serif'] = [font]
                plt.rcParams['axes.unicode_minus'] = False
                print(f"✓ 使用字体: {font}")
                return True
        except Exception:
            continue
    
    # 所有字体都不可用，打印警告
    print("⚠ 警告: 未找到中文字体，中文可能显示为方块")
    return False


class BaseChart(ABC):
    """图表基类"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.figure = None
        self.ax = None
    
    @abstractmethod
    def create(self, data: Dict[str, Any], **kwargs) -> Tuple[plt.Figure, plt.Axes]:
        """创建图表，子类必须实现"""
        pass
    
    def save(self, filepath: str, dpi: int = 150) -> None:
        """保存图表为PNG"""
        if self.figure is None:
            raise ValueError("图表尚未创建，请先调用 create()")
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.figure.savefig(filepath, dpi=dpi, bbox_inches='tight')
        print(f"✓ 图表已保存: {filepath}")
    
    def show(self) -> None:
        """显示图表"""
        if self.figure:
            plt.show()
    
    def _get_color(self, key: str, default: str = None) -> str:
        """获取颜色"""
        return self.config.get('colors', {}).get(key, default or COLORS['primary'])
    
    def _format_number(self, value: float, precision: int = 2) -> str:
        """格式化数字"""
        if np.isnan(value) or np.isinf(value):
            return "N/A"
        return f"{value:.{precision}f}"


class LineChart(BaseChart):
    """折线图"""
    
    def create(self, data: Dict[str, Any], **kwargs) -> Tuple[plt.Figure, plt.Axes]:
        years = data.get('years', [])
        y_series = data.get('y_series', [])
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        for i, (name, values) in enumerate(y_series):
            color = kwargs.get('colors', COLORS['series'])[i % len(COLORS['series'])]
            marker = kwargs.get('markers', ['o', 's', '^', 'D'])[i % 4]
            ax.plot(years, values, label=name, marker=marker, color=color, linewidth=2)
        
        ax.set_xlabel(kwargs.get('xlabel', '年份'), fontsize=12)
        ax.set_ylabel(kwargs.get('ylabel', '数值'), fontsize=12)
        ax.set_title(kwargs.get('title', '折线图'), fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        
        self.figure = fig
        self.ax = ax
        return fig, ax


class DualAxisLineChart(LineChart):
    """双轴折线图"""
    
    def create(self, data: Dict[str, Any], **kwargs) -> Tuple[plt.Figure, plt.Axes]:
        years = data.get('years', [])
        y1_series = data.get('y1_series', [])  # 左轴数据
        y2_series = data.get('y2_series', [])  # 右轴数据
        
        fig, ax1 = plt.subplots(figsize=(12, 8))
        
        # 左轴
        for i, (name, values) in enumerate(y1_series):
            color = kwargs.get('colors', COLORS['series'])[i % len(COLORS['series'])]
            ax1.plot(years, values, label=name, marker='o', color=color, linewidth=2)
        
        ax1.set_xlabel(kwargs.get('xlabel', '年份'), fontsize=12)
        ax1.set_ylabel(kwargs.get('ylabel1', '左轴数值'), fontsize=12, color=COLORS['primary'])
        ax1.tick_params(axis='y', labelcolor=COLORS['primary'])
        
        # 右轴
        ax2 = ax1.twinx()
        for i, (name, values) in enumerate(y2_series):
            color = kwargs.get('colors2', [COLORS['accent'], COLORS['secondary']])[i]
            ax2.plot(years, values, label=name, marker='^', color=color, linewidth=2, linestyle='--')
        
        ax2.set_ylabel(kwargs.get('ylabel2', '右轴数值'), fontsize=12, color=COLORS['accent'])
        ax2.tick_params(axis='y', labelcolor=COLORS['accent'])
        
        # 合并图例
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')
        
        ax1.grid(True, alpha=0.3)
        ax1.set_title(kwargs.get('title', '双轴折线图'), fontsize=14, fontweight='bold')
        
        self.figure = fig
        self.ax = ax1
        return fig, ax1


class BarChart(BaseChart):
    """柱状图"""
    
    def create(self, data: Dict[str, Any], **kwargs) -> Tuple[plt.Figure, plt.Axes]:
        years = data.get('years', [])
        y_series = data.get('y_series', [])
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        x = np.arange(len(years))
        width = 0.8 / len(y_series)
        
        for i, (name, values) in enumerate(y_series):
            color = kwargs.get('colors', COLORS['series'])[i % len(COLORS['series'])]
            offset = (i - len(y_series) / 2 + 0.5) * width
            ax.bar(x + offset, values, width, label=name, color=color)
        
        ax.set_xlabel(kwargs.get('xlabel', '年份'), fontsize=12)
        ax.set_ylabel(kwargs.get('ylabel', '数值'), fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(years)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_title(kwargs.get('title', '柱状图'), fontsize=14, fontweight='bold')
        
        self.figure = fig
        self.ax = ax
        return fig, ax


class StackedChart(BaseChart):
    """堆叠图（柱状/面积）"""
    
    def create(self, data: Dict[str, Any], **kwargs) -> Tuple[plt.Figure, plt.Axes]:
        chart_type = kwargs.get('type', 'bar')  # 'bar' or 'area'
        years = data.get('years', [])
        y_series = data.get('y_series', [])
        
        if chart_type == 'area':
            fig, ax = plt.subplots(figsize=(12, 8))
            colors = kwargs.get('colors', COLORS['series'])
            
            # 堆叠面积图
            ax.stackplot(years, *y_series, labels=kwargs.get('labels', [f'Series {i}' for i in range(len(y_series))]),
                        colors=colors[:len(y_series)], alpha=0.7)
            
            ax.set_xlabel(kwargs.get('xlabel', '年份'), fontsize=12)
            ax.set_ylabel(kwargs.get('ylabel', '数值'), fontsize=12)
            ax.legend(loc='best')
            ax.grid(True, alpha=0.3)
            ax.set_title(kwargs.get('title', '堆叠面积图'), fontsize=14, fontweight='bold')
        else:
            # 堆叠柱状图
            fig, ax = plt.subplots(figsize=(12, 8))
            x = np.arange(len(years))
            bottom = np.zeros(len(years))
            colors = kwargs.get('colors', COLORS['series'])
            
            for i, (name, values) in enumerate(y_series):
                ax.bar(x, values, bottom=bottom, label=name, color=colors[i % len(colors)])
                bottom += values
            
            ax.set_xticks(x)
            ax.set_xticklabels(years)
            ax.legend(loc='best')
            ax.grid(True, alpha=0.3, axis='y')
            ax.set_title(kwargs.get('title', '堆叠柱状图'), fontsize=14, fontweight='bold')
        
        self.figure = fig
        self.ax = ax
        return fig, ax


class BarLineCombinationChart(BaseChart):
    """柱状+折线组合图"""
    
    def create(self, data: Dict[str, Any], **kwargs) -> Tuple[plt.Figure, plt.Axes]:
        years = data.get('years', [])
        bar_series = data.get('bar_series', [])
        line_series = data.get('line_series', [])
        
        fig, ax1 = plt.subplots(figsize=(12, 8))
        
        # 柱状图（左轴）
        x = np.arange(len(years))
        width = 0.35
        colors_bar = kwargs.get('bar_colors', COLORS['series'][:len(bar_series)])
        
        for i, (name, values) in enumerate(bar_series):
            offset = (i - len(bar_series) / 2 + 0.5) * width
            ax1.bar(x + offset, values, width, label=name, color=colors_bar[i], alpha=0.8)
        
        ax1.set_xlabel(kwargs.get('xlabel', '年份'), fontsize=12)
        ax1.set_ylabel(kwargs.get('ylabel1', '柱状数值'), fontsize=12)
        ax1.set_xticks(x)
        ax1.set_xticklabels(years)
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3, axis='y')
        
        # 折线图（右轴）
        ax2 = ax1.twinx()
        colors_line = kwargs.get('line_colors', [COLORS['accent'], COLORS['primary']])
        
        for i, (name, values) in enumerate(line_series):
            ax2.plot(years, values, label=name, marker='o', color=colors_line[i], 
                    linewidth=2.5, markersize=8)
        
        ax2.set_ylabel(kwargs.get('ylabel2', '折线数值'), fontsize=12)
        ax2.legend(loc='upper right')
        
        ax1.set_title(kwargs.get('title', '柱线组合图'), fontsize=14, fontweight='bold')
        
        self.figure = fig
        self.ax = ax1
        return fig, ax1


class RadarChart(BaseChart):
    """雷达图"""
    
    def create(self, data: Dict[str, Any], **kwargs) -> Tuple[plt.Figure, plt.Axes]:
        categories = data.get('categories', [])
        values = data.get('values', [])
        
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
        
        # 闭合雷达图
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        values_plot = values + [values[0]]
        angles += angles[:1]
        
        ax.plot(angles, values_plot, 'o-', linewidth=2, color=COLORS['secondary'])
        ax.fill(angles, values_plot, alpha=0.25, color=COLORS['secondary'])
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_title(kwargs.get('title', '雷达图'), fontsize=14, fontweight='bold', pad=20)
        
        self.figure = fig
        self.ax = ax
        return fig, ax


class HeatmapChart(BaseChart):
    """热力图"""
    
    def create(self, data: Dict[str, Any], **kwargs) -> Tuple[plt.Figure, plt.Axes]:
        import seaborn as sns
        
        matrix = data.get('matrix', [])
        x_labels = data.get('x_labels', [])
        y_labels = data.get('y_labels', [])
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        cmap = kwargs.get('cmap', 'RdYlGn_r')
        sns.heatmap(matrix, xticklabels=x_labels, yticklabels=y_labels, 
                   cmap=cmap, annot=kwargs.get('annot', True), 
                   fmt='.2f', ax=ax, cbar_kws={'label': kwargs.get('cbar_label', '数值')})
        
        ax.set_title(kwargs.get('title', '热力图'), fontsize=14, fontweight='bold')
        
        self.figure = fig
        self.ax = ax
        return fig, ax


class DashboardChart(BaseChart):
    """组合仪表盘"""
    
    def create(self, data: Dict[str, Any], **kwargs) -> Tuple[plt.Figure, plt.Axes]:
        layout = kwargs.get('layout', {'rows': 2, 'cols': 3})
        rows = layout.get('rows', 2)
        cols = layout.get('cols', 3)
        
        fig, axes = plt.subplots(rows, cols, figsize=(15, 10))
        fig.suptitle(kwargs.get('title', '核心指标仪表盘'), fontsize=16, fontweight='bold')
        
        # 将axes展平为1D数组
        axes_flat = axes.flatten() if hasattr(axes, 'flatten') else [axes]
        
        metrics = data.get('metrics', {})
        
        # 简化的仪表盘：显示关键指标卡片
        metric_names = list(metrics.keys())
        
        for idx, ax in enumerate(axes_flat):
            ax.set_axis_off()
            
            if idx < len(metric_names):
                name = metric_names[idx]
                value = metrics.get(name, 'N/A')
                
                # 绘制指标卡片
                ax.text(0.5, 0.7, name, ha='center', va='center', fontsize=14, fontweight='bold')
                ax.text(0.5, 0.4, str(value), ha='center', va='center', fontsize=24, 
                       color=COLORS['secondary'])
        
        plt.tight_layout()
        
        self.figure = fig
        self.ax = axes_flat[0]
        return fig, axes_flat[0]


class ChartFactory:
    """图表工厂"""
    
    CHART_TYPES = {
        'line': LineChart,
        'dual_axis_line': DualAxisLineChart,
        'bar': BarChart,
        'stacked_bar': StackedChart,
        'stacked_area': StackedChart,
        'bar_line_combination': BarLineCombinationChart,
        'radar': RadarChart,
        'heatmap': HeatmapChart,
        'dashboard': DashboardChart,
    }
    
    @classmethod
    def create(cls, chart_type: str, config: Optional[Dict] = None) -> BaseChart:
        """创建指定类型的图表"""
        chart_class = cls.CHART_TYPES.get(chart_type)
        if chart_class is None:
            raise ValueError(f"不支持的图表类型: {chart_type}")
        return chart_class(config)
    
    @classmethod
    def register(cls, chart_type: str, chart_class: type) -> None:
        """注册新的图表类型"""
        cls.CHART_TYPES[chart_type] = chart_class


# 便捷函数：初始化图表环境
def init_chart_env(config_path: Optional[str] = None):
    """初始化图表环境（设置字体、样式）"""
    setup_chinese_font()
    
    # 设置样式
    config = ChartConfig.load(config_path)
    style = config.get('global', {}).get('style', 'seaborn-v0_8-whitegrid')
    try:
        plt.style.use(style)
    except:
        plt.style.use('default')
    
    print("✓ 图表环境已初始化")


if __name__ == '__main__':
    init_chart_env()
    print("ChartFactory 模块")
    print("支持的图表类型:", list(ChartFactory.CHART_TYPES.keys()))