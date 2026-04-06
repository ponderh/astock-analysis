# -*- coding: utf-8 -*-
"""
报告生成器 - 模块8组件

负责：
1. 生成结构化结论
2. 生成投资理由摘要
3. 输出JSON/字典格式
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime
import json

from scoring_model import InvestmentConclusion, ScoreDetails
from aggregator import AggregatedData


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        pass
    
    def generate(
        self,
        conclusion: InvestmentConclusion,
        format: str = 'dict'
    ) -> Dict:
        """
        生成分析报告
        
        Args:
            conclusion: 投资结论
            format: 输出格式 ('dict', 'json', 'summary')
            
        Returns:
            报告字典或JSON字符串
        """
        if format == 'json':
            return json.dumps(
                conclusion.to_dict(),
                ensure_ascii=False,
                indent=2
            )
        
        # dict格式
        return conclusion.to_dict()
    
    def generate_summary_report(
        self,
        conclusion: InvestmentConclusion
    ) -> str:
        """
        生成简洁的文本报告
        
        Returns:
            格式化文本报告
        """
        lines = []
        
        # 标题
        lines.append(f"{'='*50}")
        lines.append(f"投资分析报告 - {conclusion.stock_code} {conclusion.stock_name}")
        lines.append(f"{'='*50}")
        
        # 评级
        rec_symbols = {
            '强烈买入': '⬆⬆⬆⬆⬆',
            '买入': '⬆⬆⬆⬆',
            '持有': '➡➡➡',
            '卖出': '⬇⬇',
            '强烈卖出': '⬇⬇⬇⬇⬇',
        }
        symbols = rec_symbols.get(conclusion.recommendation, '?')
        lines.append(f"\n【投资建议】{conclusion.recommendation} {symbols}")
        lines.append(f"【综合评分】{conclusion.total_score:.1f}/100")
        lines.append(f"【置信度】{conclusion.confidence:.1f}%")
        
        # 评分雷达
        if conclusion.scores:
            lines.append(f"\n【评分明细】")
            scores = conclusion.scores
            lines.append(f"  财务健康: {scores.financial_health:.1f} (权重30%)")
            lines.append(f"  风险评分: {scores.risk_score:.1f} (权重25%)")
            lines.append(f"  质地评分: {scores.quality_score:.1f} (权重20%)")
            lines.append(f"  动量评分: {scores.momentum_score:.1f} (权重15%)")
            lines.append(f"  治理评分: {scores.governance_score:.1f} (权重10%)")
        
        # 风险标记
        if conclusion.has_red_flag:
            lines.append(f"\n【风险标记】⚠️ 存在红旗警示")
            lines.append(f"  红旗级别: {conclusion.red_flag_level}")
            lines.append(f"  红旗数量: {conclusion.red_flag_count}")
        
        if conclusion.has_financial_warning:
            lines.append(f"  ⚠️ 财务红灯")
        
        if conclusion.has_governance_warning:
            lines.append(f"  ⚠️ 治理红灯")
        
        # 风险列表
        if conclusion.risks:
            lines.append(f"\n【风险因素】")
            for i, risk in enumerate(conclusion.risks[:5], 1):
                lines.append(f"  {i}. {risk}")
        
        # 摘要
        if conclusion.summary:
            lines.append(f"\n【分析摘要】{conclusion.summary}")
        
        # 时间
        lines.append(f"\n【生成时间】{conclusion.timestamp}")
        lines.append(f"{'='*50}")
        
        return "\n".join(lines)
    
    def generate_api_response(
        self,
        conclusion: InvestmentConclusion
    ) -> Dict:
        """
        生成API响应格式
        
        Returns:
            标准API响应字典
        """
        return {
            'success': True,
            'data': {
                'recommendation': conclusion.recommendation,
                'confidence': conclusion.confidence,
                'total_score': conclusion.total_score,
                'scores': {
                    'financial_health': conclusion.scores.financial_health if conclusion.scores else 0,
                    'risk_score': conclusion.scores.risk_score if conclusion.scores else 0,
                    'quality_score': conclusion.scores.quality_score if conclusion.scores else 0,
                    'momentum_score': conclusion.scores.momentum_score if conclusion.scores else 0,
                    'governance_score': conclusion.scores.governance_score if conclusion.scores else 0,
                },
                'summary': conclusion.summary,
                'risks': conclusion.risks,
                'warnings': {
                    'has_red_flag': conclusion.has_red_flag,
                    'red_flag_level': conclusion.red_flag_level,
                    'has_financial_warning': conclusion.has_financial_warning,
                    'has_governance_warning': conclusion.has_governance_warning,
                },
                'stock_code': conclusion.stock_code,
                'stock_name': conclusion.stock_name,
                'timestamp': conclusion.timestamp,
            }
        }
    
    def generate_radar_data(
        self,
        conclusion: InvestmentConclusion
    ) -> Dict:
        """
        生成雷达图数据
        
        Returns:
            雷达图配置数据
        """
        if not conclusion.scores:
            return {}
        
        scores = conclusion.scores
        
        return {
            'dimensions': [
                {'name': '财务健康', 'value': scores.financial_health, 'weight': 30},
                {'name': '风险控制', 'value': scores.risk_score, 'weight': 25},
                {'name': '质地评分', 'value': scores.quality_score, 'weight': 20},
                {'name': '动量评分', 'value': scores.momentum_score, 'weight': 15},
                {'name': '公司治理', 'value': scores.governance_score, 'weight': 10},
            ],
            'total_score': conclusion.total_score,
            'recommendation': conclusion.recommendation,
        }
    
    def generate_comparison_table(
        self,
        conclusions: List[InvestmentConclusion]
    ) -> List[Dict]:
        """
        生成对比表格数据
        
        Returns:
            表格行数据列表
        """
        rows = []
        
        for c in conclusions:
            rows.append({
                '股票代码': c.stock_code,
                '股票名称': c.stock_name,
                '投资建议': c.recommendation,
                '综合评分': c.total_score,
                '置信度': c.confidence,
                '财务健康': c.scores.financial_health if c.scores else 0,
                '风险评分': c.scores.risk_score if c.scores else 0,
                '质地评分': c.scores.quality_score if c.scores else 0,
                '动量评分': c.scores.momentum_score if c.scores else 0,
                '治理评分': c.scores.governance_score if c.scores else 0,
                '红旗': c.red_flag_level if c.has_red_flag else '无',
            })
        
        return rows


# 便捷函数
def create_conclusion(**kwargs) -> InvestmentConclusion:
    """便捷创建投资结论"""
    return InvestmentConclusion(**kwargs)


def format_recommendation(recommendation: str) -> str:
    """格式化投资建议为中文全称"""
    mapping = {
        'strongly_buy': '强烈买入',
        'buy': '买入',
        'hold': '持有',
        'sell': '卖出',
        'strongly_sell': '强烈卖出',
    }
    return mapping.get(recommendation, recommendation)
