# -*- coding: utf-8 -*-
"""
结果聚合器 - 聚合模块2+5+6+7+9的数据

负责：
1. 从各模块获取数据
2. 数据标准化
3. 缺失值处理
4. 统一输出格式
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

import config as cfg
from scoring_model import ScoreDetails

logger = logging.getLogger(__name__)


# 标准化的输入数据结构
@dataclass
class AggregatedData:
    """聚合后的标准数据结构"""
    stock_code: str
    year: int
    stock_name: str = ""
    
    # 模块2：财务数据
    financial_data: Dict[str, Any] = field(default_factory=dict)
    has_financial_data: bool = False
    
    # 模块5：红旗数据
    red_flag_data: Dict[str, Any] = field(default_factory=dict)
    has_red_flag_data: bool = False
    
    # 模块6：MD&A数据
    mda_data: Dict[str, Any] = field(default_factory=dict)
    has_mda_data: bool = False
    
    # 模块7：公告数据
    announcement_data: Dict[str, Any] = field(default_factory=dict)
    has_announcement_data: bool = False
    
    # 模块9：治理数据
    governance_data: Dict[str, Any] = field(default_factory=dict)
    has_governance_data: bool = False
    
    # 缺失模块列表
    missing_modules: List[str] = field(default_factory=list)
    
    # 时间戳
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            'stock_code': self.stock_code,
            'year': self.year,
            'stock_name': self.stock_name,
            'financial_data': self.financial_data,
            'has_financial_data': self.has_financial_data,
            'red_flag_data': self.red_flag_data,
            'has_red_flag_data': self.has_red_flag_data,
            'mda_data': self.mda_data,
            'has_mda_data': self.has_mda_data,
            'announcement_data': self.announcement_data,
            'has_announcement_data': self.has_announcement_data,
            'governance_data': self.governance_data,
            'has_governance_data': self.has_governance_data,
            'missing_modules': self.missing_modules,
            'timestamp': self.timestamp,
        }


class ResultAggregator:
    """结果聚合器"""
    
    def __init__(self):
        self.default_scores = cfg.DEFAULT_SCORES
        self.missing_strategy = cfg.MISSING_STRATEGY
    
    def aggregate(
        self,
        stock_code: str,
        year: int = 2024,
        stock_name: str = "",
        # 模块2数据
        financial_data: Optional[Dict] = None,
        # 模块5数据
        red_flag_data: Optional[Dict] = None,
        # 模块6数据
        mda_data: Optional[Dict] = None,
        # 模块7数据
        announcement_data: Optional[Dict] = None,
        # 模块9数据
        governance_data: Optional[Dict] = None,
    ) -> AggregatedData:
        """
        聚合所有模块数据
        
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
            AggregatedData: 聚合后的标准数据结构
        """
        result = AggregatedData(
            stock_code=stock_code,
            year=year,
            stock_name=stock_name,
        )
        
        # 处理财务数据（模块2）
        if financial_data:
            result.financial_data = self._normalize_financial(financial_data)
            result.has_financial_data = True
        else:
            result.missing_modules.append('module2_financial')
            logger.warning(f"股票 {stock_code} 财务数据缺失，使用默认值")
        
        # 处理红旗数据（模块5）
        if red_flag_data:
            result.red_flag_data = self._normalize_red_flag(red_flag_data)
            result.has_red_flag_data = True
        else:
            result.missing_modules.append('module5_red_flag')
            logger.warning(f"股票 {stock_code} 红旗数据缺失，使用默认值")
        
        # 处理MD&A数据（模块6）
        if mda_data:
            result.mda_data = self._normalize_mda(mda_data)
            result.has_mda_data = True
        else:
            result.missing_modules.append('module6_mda')
            logger.warning(f"股票 {stock_code} MD&A数据缺失，使用默认值")
        
        # 处理公告数据（模块7）
        if announcement_data:
            result.announcement_data = self._normalize_announcement(announcement_data)
            result.has_announcement_data = True
        else:
            result.missing_modules.append('module7_announcements')
            logger.warning(f"股票 {stock_code} 公告数据缺失，使用默认值")
        
        # 处理治理数据（模块9）
        if governance_data:
            result.governance_data = self._normalize_governance(governance_data)
            result.has_governance_data = True
        else:
            result.missing_modules.append('module9_governance')
            logger.warning(f"股票 {stock_code} 治理数据缺失，使用默认值")
        
        return result
    
    def _normalize_financial(self, data: Dict) -> Dict:
        """标准化财务数据"""
        normalized = {}
        
        # 核心指标映射
        key_map = {
            'roe': ['roe', '净资产收益率', 'return_on_equity'],
            'revenue_growth': ['revenue_growth', '营收增长', 'revenue_year_over_year'],
            'net_profit_cash_ratio': ['net_profit_cash_ratio', '净利润现金含量', 'cash_to_net_profit'],
            'gross_margin': ['gross_margin', '毛利率', 'gross_profit_margin'],
            'debt_ratio': ['debt_ratio', '资产负债率', 'debt_to_asset'],
        }
        
        for standard_key, possible_keys in key_map.items():
            for key in possible_keys:
                if key in data:
                    normalized[standard_key] = data[key]
                    break
            else:
                normalized[standard_key] = None
        
        return normalized
    
    def _normalize_red_flag(self, data: Dict) -> Dict:
        """标准化红旗数据"""
        normalized = {}
        
        # 红旗分数
        if 'score' in data:
            normalized['score'] = float(data['score'])
        elif 'red_flag_score' in data:
            normalized['score'] = float(data['red_flag_score'])
        elif 'total_score' in data:
            normalized['score'] = float(data['total_score'])
        else:
            normalized['score'] = None
        
        # 红旗判定
        if 'verdict' in data:
            normalized['verdict'] = data['verdict']
        elif 'level' in data:
            normalized['verdict'] = data['level']
        elif 'risk_level' in data:
            normalized['verdict'] = data['risk_level']
        else:
            normalized['verdict'] = 'NONE'
        
        # 红旗列表
        if 'red_flags' in data:
            normalized['red_flags'] = data['red_flags']
        elif 'flags' in data:
            normalized['red_flags'] = data['flags']
        else:
            normalized['red_flags'] = []
        
        # 红旗数量
        normalized['count'] = len(normalized.get('red_flags', []))
        
        return normalized
    
    def _normalize_mda(self, data: Dict) -> Dict:
        """标准化MD&A数据"""
        normalized = {}
        
        # 战略主题
        if 'strategic_themes' in data:
            normalized['strategic_themes'] = data['strategic_themes']
        elif 'themes' in data:
            normalized['strategic_themes'] = data['themes']
        else:
            normalized['strategic_themes'] = []
        
        # 业务优势
        if 'business_strengths' in data:
            normalized['business_strengths'] = data['business_strengths']
        elif 'strengths' in data:
            normalized['business_strengths'] = data['strengths']
        else:
            normalized['business_strengths'] = []
        
        # 风险因素
        if 'risks' in data:
            normalized['risks'] = data['risks']
        elif 'risk_factors' in data:
            normalized['risks'] = data['risk_factors']
        else:
            normalized['risks'] = []
        
        # 风险数量
        normalized['risk_count'] = len(normalized.get('risks', []))
        
        return normalized
    
    def _normalize_announcement(self, data: Dict) -> Dict:
        """标准化公告数据"""
        normalized = {}
        
        # 情感分数
        if 'sentiment_score' in data:
            normalized['sentiment_score'] = float(data['sentiment_score'])
        elif 'sentiment' in data:
            val = data['sentiment']
            if isinstance(val, str):
                # 字符串转换
                sentiment_map = {
                    'very_negative': -1.0,
                    'negative': -0.5,
                    'neutral': 0.0,
                    'positive': 0.5,
                    'very_positive': 1.0,
                }
                normalized['sentiment_score'] = sentiment_map.get(val, 0.0)
            else:
                normalized['sentiment_score'] = float(val)
        else:
            normalized['sentiment_score'] = None
        
        # 情感标签
        if 'sentiment_label' in data:
            normalized['sentiment_label'] = data['sentiment_label']
        elif 'label' in data:
            normalized['sentiment_label'] = data['label']
        else:
            normalized['sentiment_label'] = None
        
        # 近期公告数量
        if 'recent_count' in data:
            normalized['recent_count'] = data['recent_count']
        elif 'count' in data:
            normalized['recent_count'] = data['count']
        else:
            normalized['recent_count'] = 0
        
        return normalized
    
    def _normalize_governance(self, data: Dict) -> Dict:
        """标准化治理数据"""
        normalized = {}
        
        # 治理分数
        if 'score' in data:
            normalized['score'] = float(data['score'])
        elif 'governance_score' in data:
            normalized['score'] = float(data['governance_score'])
        elif 'total_score' in data:
            normalized['score'] = float(data['total_score'])
        else:
            normalized['score'] = None
        
        # 治理等级
        if 'grade' in data:
            normalized['grade'] = data['grade']
        elif 'rating' in data:
            normalized['grade'] = data['rating']
        else:
            normalized['grade'] = None
        
        # 详细评分项
        if 'details' in data:
            normalized['details'] = data['details']
        else:
            normalized['details'] = {}
        
        return normalized
    
    def to_score_details(self, aggregated: AggregatedData) -> ScoreDetails:
        """
        将聚合数据转换为评分详情
        
        应用缺失容错策略
        """
        scores = ScoreDetails()
        source_flags = {}
        
        # 财务健康评分（模块2）
        if aggregated.has_financial_data:
            fin = aggregated.financial_data
            scores.financial_health = self._calculate_financial_health(fin)
            source_flags['financial_health'] = True
        else:
            scores.financial_health = self.default_scores['financial_health']
            source_flags['financial_health'] = False
        
        # 风险评分（模块5）
        if aggregated.has_red_flag_data:
            rf = aggregated.red_flag_data
            scores.risk_score = 100 - rf.get('score', 50)  # 反转
            source_flags['risk_score'] = True
        else:
            scores.risk_score = self.default_scores['risk_score']
            source_flags['risk_score'] = False
        
        # 质地评分（模块6）
        if aggregated.has_mda_data:
            mda = aggregated.mda_data
            base = 50.0
            if mda.get('strategic_themes'):
                base += min(len(mda['strategic_themes']) * 5, 20)
            if mda.get('business_strengths'):
                base += min(len(mda['business_strengths']) * 5, 15)
            if mda.get('risks'):
                base -= min(len(mda['risks']) * 8, 25)
            scores.quality_score = max(0, min(100, base))
            source_flags['quality_score'] = True
        else:
            scores.quality_score = self.default_scores['quality_score']
            source_flags['quality_score'] = False
        
        # 动量评分（模块7）
        if aggregated.has_announcement_data:
            ann = aggregated.announcement_data
            sent = ann.get('sentiment_score')
            if sent is not None:
                scores.momentum_score = (sent + 1) * 50
            else:
                scores.momentum_score = 50
            scores.momentum_score = max(0, min(100, scores.momentum_score))
            source_flags['momentum_score'] = True
        else:
            scores.momentum_score = self.default_scores['momentum_score']
            source_flags['momentum_score'] = False
        
        # 治理评分（模块9）
        if aggregated.has_governance_data:
            gov = aggregated.governance_data
            scores.governance_score = gov.get('score', 50) or 50
            source_flags['governance_score'] = True
        else:
            scores.governance_score = self.default_scores['governance_score']
            source_flags['governance_score'] = False
        
        scores._source_flags = source_flags
        return scores
    
    def _calculate_financial_health(self, fin: Dict) -> float:
        """计算财务健康评分"""
        scores = {}
        
        # ROE
        roe = fin.get('roe')
        if roe is not None:
            if roe >= 15:
                scores['roe'] = min(100, 90 + (roe - 15) * 2)
            elif roe >= 10:
                scores['roe'] = 70 + (roe - 10) * 4
            elif roe >= 5:
                scores['roe'] = 50 + (roe - 5) * 4
            else:
                scores['roe'] = max(0, 50 + roe * 10)
        else:
            scores['roe'] = 50
        
        # 营收增长
        rev_growth = fin.get('revenue_growth')
        if rev_growth is not None:
            if rev_growth >= 20:
                scores['revenue_growth'] = 90
            elif rev_growth >= 10:
                scores['revenue_growth'] = 70 + (rev_growth - 10) * 2
            elif rev_growth >= 0:
                scores['revenue_growth'] = 50 + rev_growth * 2
            else:
                scores['revenue_growth'] = max(0, 50 + rev_growth)
        else:
            scores['revenue_growth'] = 50
        
        # 现金流比例
        npc_ratio = fin.get('net_profit_cash_ratio')
        if npc_ratio is not None:
            if npc_ratio >= 100:
                scores['npc_ratio'] = 90
            elif npc_ratio >= 80:
                scores['npc_ratio'] = 70 + (npc_ratio - 80)
            elif npc_ratio >= 50:
                scores['npc_ratio'] = 50 + (npc_ratio - 50) * 0.67
            else:
                scores['npc_ratio'] = max(0, npc_ratio)
        else:
            scores['npc_ratio'] = 50
        
        # 毛利率
        gross = fin.get('gross_margin')
        if gross is not None:
            if gross >= 40:
                scores['gross_margin'] = 90
            elif gross >= 25:
                scores['gross_margin'] = 60 + (gross - 25) * 2
            elif gross >= 15:
                scores['gross_margin'] = 40 + (gross - 15) * 2
            else:
                scores['gross_margin'] = max(0, gross * 2)
        else:
            scores['gross_margin'] = 50
        
        # 负债率
        debt = fin.get('debt_ratio')
        if debt is not None:
            if debt <= 30:
                scores['debt_ratio'] = 90
            elif debt <= 50:
                scores['debt_ratio'] = 70 + (50 - debt)
            elif debt <= 70:
                scores['debt_ratio'] = 50 + (70 - debt)
            else:
                scores['debt_ratio'] = max(0, 100 - debt)
        else:
            scores['debt_ratio'] = 50
        
        # 加权
        weights = {'roe': 0.30, 'revenue_growth': 0.25, 'npc_ratio': 0.20, 'gross_margin': 0.15, 'debt_ratio': 0.10}
        total = sum(scores[k] * weights[k] for k in weights)
        return round(max(0, min(100, total)), 2)
