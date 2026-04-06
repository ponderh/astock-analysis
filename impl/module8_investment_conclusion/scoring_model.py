# -*- coding: utf-8 -*-
"""
多因子评分模型 - 模块8核心组件

实现财务/风险/质地/动量/治理五个维度的评分计算
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import numpy as np
import config as cfg


@dataclass
class ScoreDetails:
    """各维度评分详情"""
    financial_health: float = 50.0          # 财务健康 (0-100)
    risk_score: float = 50.0                # 风险评分 (0-100)
    quality_score: float = 50.0             # 质地评分 (0-100)
    momentum_score: float = 50.0             # 动量评分 (0-100)
    governance_score: float = 50.0           # 治理评分 (0-100)
    
    # 原始数据来源标记
    _source_flags: Dict[str, bool] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'financial_health': self.financial_health,
            'risk_score': self.risk_score,
            'quality_score': self.quality_score,
            'momentum_score': self.momentum_score,
            'governance_score': self.governance_score,
        }
    
    def is_missing(self, dimension: str) -> bool:
        """检查某维度是否使用默认值（缺失原数据）"""
        return self._source_flags.get(dimension, False)


@dataclass
class InvestmentConclusion:
    """投资结论"""
    stock_code: str
    stock_name: str = ""
    recommendation: str = "持有"           # 强烈买入/买入/持有/卖出/强烈卖出
    confidence: float = 50.0              # 置信度 0-100
    total_score: float = 50.0              # 综合得分 0-100
    scores: Optional[ScoreDetails] = None
    
    # 红旗标记
    has_red_flag: bool = False
    red_flag_level: str = "NONE"           # EXTREME/HIGH/MEDIUM/LOW/NONE
    red_flag_count: int = 0
    
    # 财务/治理红灯
    has_financial_warning: bool = False
    has_governance_warning: bool = False
    
    # 摘要和风险
    summary: str = ""
    risks: List[str] = field(default_factory=list)
    
    # 时间戳
    timestamp: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'recommendation': self.recommendation,
            'confidence': round(self.confidence, 2),
            'total_score': round(self.total_score, 2),
            'scores': self.scores.to_dict() if self.scores else {},
            'has_red_flag': self.has_red_flag,
            'red_flag_level': self.red_flag_level,
            'red_flag_count': self.red_flag_count,
            'has_financial_warning': self.has_financial_warning,
            'has_governance_warning': self.has_governance_warning,
            'summary': self.summary,
            'risks': self.risks,
            'timestamp': self.timestamp,
        }


class ScoringModel:
    """多因子评分模型"""
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or cfg.WEIGHTS
    
    def calculate_weighted_score(self, scores: ScoreDetails) -> float:
        """计算加权综合得分"""
        score_dict = scores.to_dict()
        total = sum(
            score_dict[key] * self.weights[key]
            for key in self.weights
        )
        return round(total, 2)
    
    def map_to_recommendation(self, total_score: float) -> str:
        """将分数映射到投资建议"""
        thresholds = cfg.RECOMMENDATION_THRESHOLDS
        
        if total_score >= thresholds['strongly_buy']:
            return '强烈买入'
        elif total_score >= thresholds['buy']:
            return '买入'
        elif total_score >= thresholds['hold']:
            return '持有'
        elif total_score >= thresholds['sell']:
            return '卖出'
        else:
            return '强烈卖出'
    
    def calculate_confidence(
        self,
        scores: ScoreDetails,
        missing_modules: List[str] = None
    ) -> float:
        """
        计算置信度
        
        原则：
        1. 财务数据缺失 → 置信度上限50%
        2. 红旗EXTREME → 置信度降低
        3. 各维度数据完整度影响置信度
        """
        base_confidence = 80.0  # 基础置信度
        missing_modules = missing_modules or []
        
        # 财务数据缺失惩罚
        if 'module2_financial' in missing_modules:
            base_confidence = min(base_confidence, 50.0)
        
        # 计算数据完整度
        available_dims = sum(
            1 for dim in cfg.WEIGHTS.keys()
            if not scores.is_missing(dim)
        )
        completeness = available_dims / len(cfg.WEIGHTS)
        
        # 完整度调整
        confidence = 50 + (base_confidence - 50) * completeness
        
        # 红旗惩罚
        if scores.is_missing('risk_score') is False:
            if scores.risk_score < 30:  # 红灯
                confidence *= 0.85
        
        return round(min(max(confidence, 10), 100), 2)
    
    def apply_red_flag_priority(
        self,
        scores: ScoreDetails,
        red_flag_level: str
    ) -> Tuple[ScoreDetails, str]:
        """
        应用红旗优先级规则：
        EXTREME > 财务红灯 > 治理红灯 → 安全优先降级
        """
        scores = scores
        final_recommendation = self.map_to_recommendation(
            self.calculate_weighted_score(scores)
        )
        
        # EXTREME级别：直接降为卖出
        if red_flag_level == 'EXTREME':
            scores.risk_score = min(scores.risk_score, 20)
            final_recommendation = '卖出'
        
        # 财务红灯：降级
        elif scores.financial_health < 30:
            if final_recommendation in ['强烈买入', '买入']:
                final_recommendation = '持有'
        
        # 治理红灯：再次降级
        elif scores.governance_score < 30:
            if final_recommendation in ['强烈买入', '买入', '持有']:
                final_recommendation = '卖出'
        
        return scores, final_recommendation
    
    def score_financial_health(
        self,
        roe: Optional[float] = None,
        revenue_growth: Optional[float] = None,
        net_profit_cash_ratio: Optional[float] = None,
        gross_margin: Optional[float] = None,
        debt_ratio: Optional[float] = None,
        industry_avg: Optional[Dict] = None
    ) -> float:
        """
        计算财务健康评分
        
        指标及权重：
        - ROE (30%): 净资产收益率，越高越好
        - 营收增长 (25%): 营收同比增速
        - 现金流比例 (20%): 净利润现金含量
        - 毛利率 (15%): 毛利率水平
        - 负债率 (10%): 资产负债率，越低越好
        """
        scores = {}
        weights = {
            'roe': 0.30,
            'revenue_growth': 0.25,
            'net_profit_cash_ratio': 0.20,
            'gross_margin': 0.15,
            'debt_ratio': 0.10,
        }
        
        # ROE评分 (优秀>=15%, 良好10-15%, 及格5-10%, 差<5%)
        if roe is not None:
            if roe >= 15:
                scores['roe'] = 90 + (roe - 15) * 2  # 可超过100
            elif roe >= 10:
                scores['roe'] = 70 + (roe - 10) * 4
            elif roe >= 5:
                scores['roe'] = 50 + (roe - 5) * 4
            else:
                scores['roe'] = max(0, 50 + roe * 10)
            scores['roe'] = min(100, scores['roe'])
        else:
            scores['roe'] = 50
        
        # 营收增长评分
        if revenue_growth is not None:
            if revenue_growth >= 20:
                scores['revenue_growth'] = 90
            elif revenue_growth >= 10:
                scores['revenue_growth'] = 70 + (revenue_growth - 10) * 2
            elif revenue_growth >= 0:
                scores['revenue_growth'] = 50 + revenue_growth * 2
            else:
                scores['revenue_growth'] = max(0, 50 + revenue_growth)
        else:
            scores['revenue_growth'] = 50
        
        # 现金流比例评分
        if net_profit_cash_ratio is not None:
            if net_profit_cash_ratio >= 100:
                scores['net_profit_cash_ratio'] = 90
            elif net_profit_cash_ratio >= 80:
                scores['net_profit_cash_ratio'] = 70 + (net_profit_cash_ratio - 80) * 1
            elif net_profit_cash_ratio >= 50:
                scores['net_profit_cash_ratio'] = 50 + (net_profit_cash_ratio - 50) * 0.67
            else:
                scores['net_profit_cash_ratio'] = max(0, net_profit_cash_ratio)
        else:
            scores['net_profit_cash_ratio'] = 50
        
        # 毛利率评分
        if gross_margin is not None:
            if gross_margin >= 40:
                scores['gross_margin'] = 90
            elif gross_margin >= 25:
                scores['gross_margin'] = 60 + (gross_margin - 25) * 2
            elif gross_margin >= 15:
                scores['gross_margin'] = 40 + (gross_margin - 15) * 2
            else:
                scores['gross_margin'] = max(0, gross_margin * 2)
        else:
            scores['gross_margin'] = 50
        
        # 负债率评分 (越低越好)
        if debt_ratio is not None:
            if debt_ratio <= 30:
                scores['debt_ratio'] = 90
            elif debt_ratio <= 50:
                scores['debt_ratio'] = 70 + (50 - debt_ratio)
            elif debt_ratio <= 70:
                scores['debt_ratio'] = 50 + (70 - debt_ratio) * 1
            else:
                scores['debt_ratio'] = max(0, 100 - debt_ratio)
        else:
            scores['debt_ratio'] = 50
        
        # 加权计算
        total = sum(scores[k] * weights[k] for k in weights)
        return round(total, 2)
    
    def score_risk_from_red_flags(
        self,
        red_flag_score: Optional[float] = None,
        red_flag_verdict: Optional[str] = None,
        red_flag_count: int = 0
    ) -> float:
        """
        从红旗评分计算风险得分
        
        红旗分数越高风险越大，风险得分需要反转
        红旗分数0=无风险(100分)，100=极高风险(0分)
        """
        if red_flag_score is not None:
            # 分数反转：0-100 → 100-0
            risk_score = 100 - red_flag_score
        elif red_flag_verdict is not None:
            # 文字判断转换
            verdict_map = {
                'NONE': 100,
                'LOW': 80,
                'MEDIUM': 60,
                'HIGH': 40,
                'EXTREME': 20,
            }
            risk_score = verdict_map.get(red_flag_verdict, 50)
        else:
            risk_score = 50
        
        return round(risk_score, 2)
    
    def score_quality_from_mda(
        self,
        strategic_themes: Optional[List[str]] = None,
        business_strengths: Optional[List[str]] = None,
        risks: Optional[List[str]] = None,
        risk_count: int = 0
    ) -> float:
        """
        从MD&A分析计算质地评分
        
        考虑：
        - 战略主题丰富度
        - 业务优势数量
        - 风险暴露程度
        """
        base_score = 50.0
        
        # 战略主题加分
        if strategic_themes:
            theme_bonus = min(len(strategic_themes) * 5, 20)
            base_score += theme_bonus
        
        # 业务优势加分
        if business_strengths:
            strength_bonus = min(len(business_strengths) * 5, 15)
            base_score += strength_bonus
        
        # 风险暴露减分
        if risks:
            risk_penalty = min(len(risks) * 8, 25)
            base_score -= risk_penalty
        
        return round(max(0, min(100, base_score)), 2)
    
    def score_momentum_from_announcements(
        self,
        sentiment_score: Optional[float] = None,
        sentiment_label: Optional[str] = None,
        recent_count: int = 0
    ) -> float:
        """
        从公告情感计算动量评分
        
        情感分数 -1~1 → 0~100
        """
        if sentiment_score is not None:
            # 转换 -1~1 到 0~100
            momentum_score = (sentiment_score + 1) * 50
        elif sentiment_label is not None:
            label_map = {
                'very_negative': 20,
                'negative': 35,
                'neutral': 50,
                'positive': 65,
                'very_positive': 80,
            }
            momentum_score = label_map.get(sentiment_label, 50)
        else:
            momentum_score = 50
        
        # 近期公告数量微调
        if recent_count > 5:
            momentum_score = min(100, momentum_score + 5)
        elif recent_count == 0:
            momentum_score = max(0, momentum_score - 10)
        
        return round(max(0, min(100, momentum_score)), 2)
    
    def score_governance(
        self,
        governance_score: Optional[float] = None,
        governance_grade: Optional[str] = None
    ) -> float:
        """
        计算治理评分
        
        分数直接使用，或从等级转换
        """
        if governance_score is not None:
            return round(governance_score, 2)
        
        if governance_grade is not None:
            grade_map = {
                'A': 90,
                'B': 75,
                'C': 55,
                'D': 35,
                'E': 15,
            }
            return round(grade_map.get(governance_grade, 50), 2)
        
        return 50.0
