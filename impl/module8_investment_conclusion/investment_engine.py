# -*- coding: utf-8 -*-
"""
投资结论引擎 - 模块8核心组件

负责：
1. 综合评分计算
2. 投资建议生成
3. 置信度计算
4. 优先级规则应用
"""

from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import logging

import config as cfg
from scoring_model import ScoringModel, ScoreDetails, InvestmentConclusion
from aggregator import ResultAggregator, AggregatedData

logger = logging.getLogger(__name__)


class InvestmentEngine:
    """投资结论引擎"""
    
    def __init__(self):
        self.scorer = ScoringModel()
        self.aggregator = ResultAggregator()
    
    def analyze(
        self,
        stock_code: str,
        year: int = 2024,
        stock_name: str = "",
        # 各模块原始数据
        financial_data: Optional[Dict] = None,
        red_flag_data: Optional[Dict] = None,
        mda_data: Optional[Dict] = None,
        announcement_data: Optional[Dict] = None,
        governance_data: Optional[Dict] = None,
    ) -> InvestmentConclusion:
        """
        综合分析单只股票
        
        Args:
            stock_code: 股票代码
            year: 分析年度
            stock_name: 股票名称
            financial_data: 模块2财务数据
            red_flag_data: 模块5红旗数据
            mda_data: 模块6 MD&A数据
            announcement_data: 模块7公告数据
            governance_data: 模块9治理数据
            
        Returns:
            InvestmentConclusion: 投资结论
        """
        # Step 1: 聚合数据
        aggregated = self.aggregator.aggregate(
            stock_code=stock_code,
            year=year,
            stock_name=stock_name,
            financial_data=financial_data,
            red_flag_data=red_flag_data,
            mda_data=mda_data,
            announcement_data=announcement_data,
            governance_data=governance_data,
        )
        
        # Step 2: 转换为评分详情
        scores = self.aggregator.to_score_details(aggregated)
        
        # Step 3: 计算加权总分
        total_score = self.scorer.calculate_weighted_score(scores)
        
        # Step 4: 获取红旗级别
        red_flag_level = 'NONE'
        red_flag_count = 0
        if aggregated.has_red_flag_data:
            rf = aggregated.red_flag_data
            verdict = rf.get('verdict', 'NONE')
            if verdict in config.RED_FLAG_PRIORITY:
                red_flag_level = verdict
            red_flag_count = rf.get('count', 0)
        
        # Step 5: 应用优先级规则
        final_scores, recommendation = self.scorer.apply_red_flag_priority(
            scores, red_flag_level
        )
        
        # 重新计算总分（应用优先级后）
        total_score = self.scorer.calculate_weighted_score(final_scores)
        
        # 如果优先级规则已经给出了建议，使用它
        if red_flag_level == 'EXTREME':
            recommendation = '卖出'
            total_score = min(total_score, 30)
        elif red_flag_level == 'HIGH':
            if recommendation in ['强烈买入', '买入']:
                recommendation = '持有'
        elif final_scores.financial_health < 30:
            if recommendation in ['强烈买入']:
                recommendation = '买入'
        
        # Step 6: 计算置信度
        confidence = self.scorer.calculate_confidence(
            final_scores, aggregated.missing_modules
        )
        
        # 额外置信度惩罚
        if red_flag_level == 'EXTREME':
            confidence = confidence * 0.6
        elif red_flag_level == 'HIGH':
            confidence = confidence * 0.8
        
        confidence = round(max(10, min(100, confidence)), 2)
        
        # Step 7: 判断财务/治理红灯
        has_financial_warning = final_scores.financial_health < 30
        has_governance_warning = final_scores.governance_score < 30
        
        # Step 8: 生成风险列表
        risks = self._generate_risk_list(aggregated, final_scores)
        
        # Step 9: 生成摘要
        summary = self._generate_summary(
            stock_code, recommendation, total_score, final_scores, risks
        )
        
        # 构建结论
        conclusion = InvestmentConclusion(
            stock_code=stock_code,
            stock_name=stock_name,
            recommendation=recommendation,
            confidence=confidence,
            total_score=total_score,
            scores=final_scores,
            has_red_flag=(red_flag_level != 'NONE'),
            red_flag_level=red_flag_level,
            red_flag_count=red_flag_count,
            has_financial_warning=has_financial_warning,
            has_governance_warning=has_governance_warning,
            summary=summary,
            risks=risks,
            timestamp=datetime.now().isoformat(),
        )
        
        return conclusion
    
    def _generate_risk_list(
        self,
        aggregated: AggregatedData,
        scores: ScoreDetails
    ) -> List[str]:
        """生成风险列表"""
        risks = []
        
        # 红旗风险
        if aggregated.has_red_flag_data:
            rf = aggregated.red_flag_data
            flags = rf.get('red_flags', [])
            if rf.get('verdict') in ['EXTREME', 'HIGH']:
                risks.append(f"存在{rf.get('verdict')}级别红旗风险 ({len(flags)}项)")
                for flag in flags[:3]:  # 最多3条
                    risks.append(f"  - {flag}")
        
        # 财务风险
        if aggregated.has_financial_data:
            fin = aggregated.financial_data
            if fin.get('roe') is not None and fin.get('roe') < 5:
                risks.append("ROE低于5%，盈利能力较弱")
            if fin.get('net_profit_cash_ratio') is not None and fin.get('net_profit_cash_ratio') < 50:
                risks.append("净利润现金含量不足50%，盈利质量存疑")
            if fin.get('debt_ratio') is not None and fin.get('debt_ratio') > 70:
                risks.append(f"资产负债率{fin.get('debt_ratio')}%，偿债风险较高")
        
        # 治理风险
        if aggregated.has_governance_data:
            gov = aggregated.governance_data
            if gov.get('score') is not None and gov.get('score') < 40:
                risks.append(f"公司治理评分{gov.get('score')}分，存在治理风险")
        
        # MD&A风险
        if aggregated.has_mda_data:
            mda = aggregated.mda_data
            risks_list = mda.get('risks', [])
            for risk in risks_list[:3]:
                risks.append(f"MD&A风险: {risk}")
        
        return risks
    
    def _generate_summary(
        self,
        stock_code: str,
        recommendation: str,
        total_score: float,
        scores: ScoreDetails,
        risks: List[str]
    ) -> str:
        """生成100字摘要"""
        parts = []
        
        # 评级说明
        rec_emoji = {
            '强烈买入': '⭐⭐⭐⭐⭐',
            '买入': '⭐⭐⭐⭐',
            '持有': '⭐⭐⭐',
            '卖出': '⭐⭐',
            '强烈卖出': '⭐',
        }
        
        emoji = rec_emoji.get(recommendation, '⭐')
        parts.append(f"{stock_code}综合得分{total_score:.1f}分，评级{recommendation}{emoji}")
        
        # 核心因素
        factors = []
        if scores.financial_health >= 70:
            factors.append("财务健康")
        elif scores.financial_health < 30:
            factors.append("财务存疑")
        
        if scores.risk_score >= 70:
            factors.append("风险较低")
        elif scores.risk_score < 30:
            factors.append("风险较高")
        
        if scores.quality_score >= 70:
            factors.append("质地优良")
        
        if scores.momentum_score >= 65:
            factors.append("近期利好")
        elif scores.momentum_score < 35:
            factors.append("近期利空")
        
        if scores.governance_score >= 70:
            factors.append("治理良好")
        elif scores.governance_score < 30:
            factors.append("治理存疑")
        
        if factors:
            parts.append("，".join(factors) + "。")
        else:
            parts.append("各维度表现均衡。")
        
        # 风险提示（如果有）
        if risks:
            parts.append(f"注意{len(risks)}项风险因素。")
        
        summary = "".join(parts)
        
        # 截断到100字
        if len(summary) > 100:
            summary = summary[:97] + "..."
        
        return summary
    
    def batch_analyze(
        self,
        stocks: List[Dict],
    ) -> List[InvestmentConclusion]:
        """
        批量分析多只股票
        
        Args:
            stocks: 股票数据列表，每项包含:
                {
                    'stock_code': str,
                    'stock_name': str,
                    'financial_data': dict,
                    'red_flag_data': dict,
                    ...
                }
                
        Returns:
            投资结论列表
        """
        results = []
        for stock in stocks:
            conclusion = self.analyze(
                stock_code=stock.get('stock_code', ''),
                stock_name=stock.get('stock_name', ''),
                year=stock.get('year', 2024),
                financial_data=stock.get('financial_data'),
                red_flag_data=stock.get('red_flag_data'),
                mda_data=stock.get('mda_data'),
                announcement_data=stock.get('announcement_data'),
                governance_data=stock.get('governance_data'),
            )
            results.append(conclusion)
        
        return results
    
    def get_ranking(
        self,
        conclusions: List[InvestmentConclusion]
    ) -> List[InvestmentConclusion]:
        """
        对结论列表排序
        
        排序规则：强烈买入 > 买入 > 持有 > 卖出 > 强烈卖出
        同级别按总分排序
        """
        rec_order = {
            '强烈买入': 5,
            '买入': 4,
            '持有': 3,
            '卖出': 2,
            '强烈卖出': 1,
        }
        
        return sorted(
            conclusions,
            key=lambda c: (rec_order.get(c.recommendation, 0), c.total_score),
            reverse=True
        )
