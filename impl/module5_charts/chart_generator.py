# -*- coding: utf-8 -*-
"""
ChartGenerator - 图表生成器主入口
=================================
整合调用 Phase 2 的 7 张图表（图表1-6 + 图表15）
"""

import os
import sys
import argparse
from typing import Dict, List, Any, Optional
import matplotlib.pyplot as plt

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from chart_factory import init_chart_env, COLORS

# 导入各图表模块
from charts.chart_01_revenue_profit_trend import create_revenue_profit_trend
from charts.chart_02_roic_wacc_trend import create_roic_wacc_trend
from charts.chart_03_dupont_stacked import create_dupont_stacked
from charts.chart_04_eps_dps_combined import create_eps_dps_combined
from charts.chart_05_debt_ratios import create_debt_ratios_trend
from charts.chart_15_dashboard import create_advanced_dashboard


class ChartGenerator:
    """图表生成器 - 批量生成财务分析图表"""
    
    def __init__(self, stock_code: str = '000001', output_dir: str = None):
        """
        初始化图表生成器
        
        Parameters
        ----------
        stock_code : str
            股票代码
        output_dir : str
            输出目录，默认为 ./output
        """
        self.stock_code = stock_code
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), 'output')
        self.results = {}
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_all(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        生成所有 Phase 2 图表（7张）
        
        Parameters
        ----------
        data : Dict[str, Any]
            财务数据字典，需包含:
            - years: 年份列表
            - revenue: 营业收入
            - net_profit: 净利润
            - roic: ROIC列表
            - wacc: WACC列表
            - dupont_net_margin: 杜邦净利率
            - dupont_asset_turnover: 杜邦资产周转率
            - dupont_equity_multiplier: 杜邦权益乘数
            - eps: 每股收益
            - dps: 每股分红
            - cumulative_dps: 累计分红
            - debt_ratio: 资产负债率
            - interest_bearing_debt_ratio: 有息负债率
            - (可选) 综合指标用于仪表盘
            
        Returns
        -------
        Dict[str, str]
            图表ID到文件路径的映射
        """
        years = data.get('years', [])
        results = {}
        
        print(f"\n{'='*50}")
        print(f"开始生成 {self.stock_code} 的财务图表...")
        print(f"{'='*50}\n")
        
        # 图表1: 营收/净利润趋势
        print("[1/7] 生成 营收/净利润趋势...")
        try:
            fig, ax = create_revenue_profit_trend(
                years,
                data.get('revenue', []),
                data.get('net_profit', []),
                output_dir=self.output_dir,
                stock_code=self.stock_code
            )
            results['chart_01'] = os.path.join(self.output_dir, f'{self.stock_code}_chart01_revenue_profit_trend.png')
            plt.close(fig)
        except Exception as e:
            print(f"  ✗ 图表1生成失败: {e}")
        
        # 图表2: ROIC vs WACC趋势
        print("[2/7] 生成 ROIC vs WACC趋势...")
        try:
            fig, ax = create_roic_wacc_trend(
                years,
                data.get('roic', []),
                data.get('wacc', []),
                output_dir=self.output_dir,
                stock_code=self.stock_code
            )
            results['chart_02'] = os.path.join(self.output_dir, f'{self.stock_code}_chart02_roic_wacc_trend.png')
            plt.close(fig)
        except Exception as e:
            print(f"  ✗ 图表2生成失败: {e}")
        
        # 图表3: 杜邦三因子贡献堆叠
        print("[3/7] 生成 杜邦三因子贡献堆叠...")
        try:
            fig, ax = create_dupont_stacked(
                years,
                data.get('dupont_net_margin', []),
                data.get('dupont_asset_turnover', []),
                data.get('dupont_equity_multiplier', []),
                output_dir=self.output_dir,
                stock_code=self.stock_code
            )
            results['chart_03'] = os.path.join(self.output_dir, f'{self.stock_code}_chart03_dupont_stacked.png')
            plt.close(fig)
        except Exception as e:
            print(f"  ✗ 图表3生成失败: {e}")
        
        # 图表4: EPS + DPS + 累计分红
        print("[4/7] 生成 EPS + DPS + 累计分红...")
        try:
            fig, ax = create_eps_dps_combined(
                years,
                data.get('eps', []),
                data.get('dps', []),
                data.get('cumulative_dps', []),
                output_dir=self.output_dir,
                stock_code=self.stock_code
            )
            results['chart_04'] = os.path.join(self.output_dir, f'{self.stock_code}_chart04_eps_dps_combined.png')
            plt.close(fig)
        except Exception as e:
            print(f"  ✗ 图表4生成失败: {e}")
        
        # 图表5: 资产负债率+有息负债率
        print("[5/7] 生成 资产负债率+有息负债率...")
        try:
            fig, ax = create_debt_ratios_trend(
                years,
                data.get('debt_ratio', []),
                data.get('interest_bearing_debt_ratio', []),
                output_dir=self.output_dir,
                stock_code=self.stock_code
            )
            results['chart_05'] = os.path.join(self.output_dir, f'{self.stock_code}_chart05_debt_ratios.png')
            plt.close(fig)
        except Exception as e:
            print(f"  ✗ 图表5生成失败: {e}")
        
        # 图表15: 核心指标仪表盘
        print("[6/7] 生成 核心指标仪表盘...")
        try:
            dashboard_metrics = data.get('dashboard_metrics', {
                'ROE': f"{data.get('roe', ['N/A'])[0] if data.get('roe') else 'N/A'}%",
                '毛利率': f"{data.get('gross_margin', ['N/A'])[0] if data.get('gross_margin') else 'N/A'}%",
                '净利率': f"{data.get('net_margin', ['N/A'])[0] if data.get('net_margin') else 'N/A'}%",
                'ROIC': f"{data.get('roic', ['N/A'])[0] if data.get('roic') else 'N/A'}%",
                '资产负债率': f"{data.get('debt_ratio', ['N/A'])[0] if data.get('debt_ratio') else 'N/A'}%",
                '股息率': f"{data.get('dividend_yield', ['N/A'])[0] if data.get('dividend_yield') else 'N/A'}%"
            })
            fig, ax = create_advanced_dashboard(
                dashboard_metrics,
                output_dir=self.output_dir,
                stock_code=self.stock_code
            )
            results['chart_15'] = os.path.join(self.output_dir, f'{self.stock_code}_chart15_dashboard.png')
            plt.close(fig)
        except Exception as e:
            print(f"  ✗ 图表15生成失败: {e}")
        
        print(f"\n{'='*50}")
        print(f"✓ 图表生成完成! 共生成 {len(results)} 张图表")
        print(f"  输出目录: {self.output_dir}")
        print(f"{'='*50}\n")
        
        self.results = results
        return results
    
    def get_results(self) -> Dict[str, str]:
        """获取生成结果"""
        return self.results


def load_sample_data() -> Dict[str, Any]:
    """加载示例数据用于测试"""
    return {
        'years': [2020, 2021, 2022, 2023, 2024],
        # 图表1: 营收/净利润
        'revenue': [100.5, 120.3, 135.8, 150.2, 168.9],
        'net_profit': [15.2, 18.5, 20.1, 22.8, 25.6],
        # 图表2: ROIC vs WACC
        'roic': [8.5, 9.2, 7.8, 10.1, 11.3],
        'wacc': [8.5, 8.5, 8.5, 8.5, 8.5],
        # 图表3: 杜邦三因子
        'dupont_net_margin': [0.15, 0.16, 0.14, 0.15, 0.17],
        'dupont_asset_turnover': [0.8, 0.85, 0.82, 0.88, 0.9],
        'dupont_equity_multiplier': [2.0, 2.1, 2.0, 1.9, 1.8],
        # 图表4: EPS/DPS/累计分红
        'eps': [1.25, 1.48, 1.62, 1.85, 2.05],
        'dps': [0.35, 0.42, 0.45, 0.52, 0.58],
        'cumulative_dps': [0.35, 0.77, 1.22, 1.74, 2.32],
        # 图表5: 资产负债率/有息负债率
        'debt_ratio': [45.2, 48.5, 50.1, 47.8, 46.3],
        'interest_bearing_debt_ratio': [28.5, 30.2, 32.5, 29.8, 27.5],
        # 图表15: 仪表盘指标
        'dashboard_metrics': {
            'ROE': '15.2%',
            '毛利率': '32.5%',
            '净利率': '18.7%',
            'ROIC': '12.3%',
            '资产负债率': '45.2%',
            '股息率': '2.8%'
        }
    }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='财务图表生成器 - Phase 2')
    parser.add_argument('--stock', type=str, default='000001', help='股票代码')
    parser.add_argument('--output', type=str, default=None, help='输出目录')
    parser.add_argument('--sample', action='store_true', help='使用示例数据')
    
    args = parser.parse_args()
    
    # 初始化图表环境
    init_chart_env()
    
    # 创建生成器
    generator = ChartGenerator(
        stock_code=args.stock,
        output_dir=args.output
    )
    
    # 加载数据
    if args.sample:
        data = load_sample_data()
    else:
        # TODO: 从模块2加载实际数据
        print("⚠ 未指定 --sample，将使用示例数据")
        data = load_sample_data()
    
    # 生成图表
    results = generator.generate_all(data)
    
    # 打印结果
    print("生成结果:")
    for chart_id, filepath in results.items():
        print(f"  {chart_id}: {filepath}")
    
    return results


if __name__ == '__main__':
    main()