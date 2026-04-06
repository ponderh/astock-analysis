# -*- coding: utf-8 -*-
"""
模块8：投资结论引擎 - 单元测试
"""

import unittest
from datetime import datetime


class TestScoringModel(unittest.TestCase):
    """测试多因子评分模型"""
    
    def setUp(self):
        from module8_investment_conclusion import ScoringModel
        self.scorer = ScoringModel()
    
    def test_calculate_weighted_score(self):
        """测试加权分数计算"""
        from module8_investment_conclusion import ScoreDetails
        
        scores = ScoreDetails(
            financial_health=80,
            risk_score=70,
            quality_score=60,
            momentum_score=75,
            governance_score=85,
        )
        
        total = self.scorer.calculate_weighted_score(scores)
        
        # 期望: 80*0.30 + 70*0.25 + 60*0.20 + 75*0.15 + 85*0.10
        # = 24 + 17.5 + 12 + 11.25 + 8.5 = 73.25
        self.assertAlmostEqual(total, 73.25, places=1)
    
    def test_map_to_recommendation(self):
        """测试分数到建议的映射"""
        # 边界值测试
        self.assertEqual(self.scorer.map_to_recommendation(85), '强烈买入')
        self.assertEqual(self.scorer.map_to_recommendation(80), '强烈买入')
        self.assertEqual(self.scorer.map_to_recommendation(70), '买入')
        self.assertEqual(self.scorer.map_to_recommendation(65), '买入')
        self.assertEqual(self.scorer.map_to_recommendation(50), '持有')
        self.assertEqual(self.scorer.map_to_recommendation(45), '持有')
        self.assertEqual(self.scorer.map_to_recommendation(35), '卖出')
        self.assertEqual(self.scorer.map_to_recommendation(30), '卖出')
        self.assertEqual(self.scorer.map_to_recommendation(20), '强烈卖出')
    
    def test_calculate_confidence(self):
        """测试置信度计算"""
        from module8_investment_conclusion import ScoreDetails
        
        # 完整数据
        scores = ScoreDetails(
            financial_health=80,
            risk_score=70,
            quality_score=60,
            momentum_score=75,
            governance_score=85,
            _source_flags={
                'financial_health': True,
                'risk_score': True,
                'quality_score': True,
                'momentum_score': True,
                'governance_score': True,
            }
        )
        
        confidence = self.scorer.calculate_confidence(scores, [])
        self.assertGreaterEqual(confidence, 50)
        
        # 缺失财务数据
        confidence_with_missing = self.scorer.calculate_confidence(
            scores, ['module2_financial']
        )
        self.assertLessEqual(confidence_with_missing, 50)
    
    def test_score_financial_health(self):
        """测试财务健康评分"""
        # 优秀财务数据
        score = self.scorer.score_financial_health(
            roe=18,
            revenue_growth=25,
            net_profit_cash_ratio=110,
            gross_margin=45,
            debt_ratio=25,
        )
        self.assertGreater(score, 80)
        
        # 差财务数据
        score = self.scorer.score_financial_health(
            roe=2,
            revenue_growth=-10,
            net_profit_cash_ratio=20,
            gross_margin=10,
            debt_ratio=80,
        )
        self.assertLessEqual(score, 40)
        
        # 缺失数据
        score = self.scorer.score_financial_health()
        self.assertEqual(score, 50)
    
    def test_score_risk_from_red_flags(self):
        """测试风险评分计算"""
        # 无风险
        score = self.scorer.score_risk_from_red_flags(red_flag_score=0)
        self.assertEqual(score, 100)
        
        # 高风险
        score = self.scorer.score_risk_from_red_flags(red_flag_score=90)
        self.assertEqual(score, 10)
        
        # 通过verdict
        score = self.scorer.score_risk_from_red_flags(red_flag_verdict='EXTREME')
        self.assertEqual(score, 20)
        
        score = self.scorer.score_risk_from_red_flags(red_flag_verdict='NONE')
        self.assertEqual(score, 100)
    
    def test_apply_red_flag_priority(self):
        """测试红旗优先级规则"""
        from module8_investment_conclusion import ScoreDetails
        
        # EXTREME级别应该降级
        scores = ScoreDetails(
            financial_health=85,
            risk_score=80,
            quality_score=75,
            momentum_score=70,
            governance_score=80,
        )
        
        new_scores, rec = self.scorer.apply_red_flag_priority(scores, 'EXTREME')
        
        self.assertEqual(rec, '卖出')
        self.assertLessEqual(new_scores.risk_score, 20)


class TestResultAggregator(unittest.TestCase):
    """测试结果聚合器"""
    
    def setUp(self):
        from module8_investment_conclusion import ResultAggregator
        self.aggregator = ResultAggregator()
    
    def test_aggregate_with_all_data(self):
        """测试完整数据聚合"""
        result = self.aggregator.aggregate(
            stock_code='000858',
            year=2024,
            stock_name='五粮液',
            financial_data={
                'roe': 15.5,
                'revenue_growth': 12.0,
                'net_profit_cash_ratio': 95,
                'gross_margin': 38,
                'debt_ratio': 35,
            },
            red_flag_data={
                'score': 10,
                'verdict': 'LOW',
                'red_flags': ['关联交易'],
            },
            mda_data={
                'strategic_themes': ['数字化转型', '品牌升级'],
                'business_strengths': ['品牌优势', '渠道优势'],
                'risks': ['原材料价格波动'],
            },
            announcement_data={
                'sentiment_score': 0.6,
                'recent_count': 8,
            },
            governance_data={
                'score': 85,
                'grade': 'A',
            },
        )
        
        self.assertEqual(result.stock_code, '000858')
        self.assertTrue(result.has_financial_data)
        self.assertTrue(result.has_red_flag_data)
        self.assertTrue(result.has_mda_data)
        self.assertTrue(result.has_announcement_data)
        self.assertTrue(result.has_governance_data)
        self.assertEqual(len(result.missing_modules), 0)
    
    def test_aggregate_with_missing_data(self):
        """测试缺失数据容错"""
        result = self.aggregator.aggregate(
            stock_code='000001',
            year=2024,
            financial_data=None,
            red_flag_data=None,
            mda_data=None,
            announcement_data=None,
            governance_data=None,
        )
        
        self.assertEqual(len(result.missing_modules), 5)
        
        # 验证使用默认值
        scores = self.aggregator.to_score_details(result)
        self.assertEqual(scores.financial_health, 50)
        self.assertEqual(scores.risk_score, 50)
        self.assertEqual(scores.quality_score, 50)
        self.assertEqual(scores.momentum_score, 50)
        self.assertEqual(scores.governance_score, 50)
    
    def test_normalize_financial(self):
        """测试财务数据标准化"""
        # 测试多种字段名映射
        result1 = self.aggregator._normalize_financial({'roe': 15})
        self.assertEqual(result1['roe'], 15)
        
        result2 = self.aggregator._normalize_financial({'净资产收益率': 15})
        self.assertEqual(result2['roe'], 15)
        
        result3 = self.aggregator._normalize_financial({'return_on_equity': 15})
        self.assertEqual(result3['roe'], 15)
    
    def test_normalize_red_flag(self):
        """测试红旗数据标准化"""
        result = self.aggregator._normalize_red_flag({
            'score': 25,
            'verdict': 'MEDIUM',
            'red_flags': ['违规', '诉讼'],
        })
        
        self.assertEqual(result['score'], 25)
        self.assertEqual(result['verdict'], 'MEDIUM')
        self.assertEqual(result['count'], 2)


class TestInvestmentEngine(unittest.TestCase):
    """测试投资结论引擎"""
    
    def setUp(self):
        from module8_investment_conclusion import InvestmentEngine
        self.engine = InvestmentEngine()
    
    def test_analyze_excellent_stock(self):
        """测试优秀股票分析"""
        result = self.engine.analyze(
            stock_code='000858',
            stock_name='五粮液',
            financial_data={
                'roe': 18.5,
                'revenue_growth': 15.0,
                'net_profit_cash_ratio': 105,
                'gross_margin': 40,
                'debt_ratio': 30,
            },
            red_flag_data={
                'score': 5,
                'verdict': 'NONE',
                'red_flags': [],
            },
            mda_data={
                'strategic_themes': ['数字化转型', '品牌升级', '国际化'],
                'business_strengths': ['品牌优势', '渠道优势', '研发优势'],
                'risks': ['原材料价格波动'],
            },
            announcement_data={
                'sentiment_score': 0.7,
                'recent_count': 10,
            },
            governance_data={
                'score': 90,
                'grade': 'A',
            },
        )
        
        self.assertIn(result.recommendation, ['强烈买入', '买入', '持有'])
        self.assertGreater(result.total_score, 60)
        self.assertGreaterEqual(result.confidence, 50)
    
    def test_analyze_poor_stock(self):
        """测试问题股票分析"""
        result = self.engine.analyze(
            stock_code='600000',
            stock_name='某问题股',
            financial_data={
                'roe': 2.5,
                'revenue_growth': -8.0,
                'net_profit_cash_ratio': 30,
                'gross_margin': 8,
                'debt_ratio': 85,
            },
            red_flag_data={
                'score': 85,
                'verdict': 'EXTREME',
                'red_flags': ['涉嫌违规', '诉讼风险', '业绩造假嫌疑'],
            },
            mda_data={
                'strategic_themes': [],
                'business_strengths': [],
                'risks': ['持续亏损', '债务危机', '管理层动荡'],
            },
            announcement_data={
                'sentiment_score': -0.8,
                'recent_count': 3,
            },
            governance_data={
                'score': 25,
                'grade': 'E',
            },
        )
        
        # EXTREME级别应被降级
        self.assertIn(result.recommendation, ['卖出', '强烈卖出'])
        self.assertTrue(result.has_red_flag)
        self.assertEqual(result.red_flag_level, 'EXTREME')
    
    def test_analyze_with_missing_data(self):
        """测试缺失数据情况"""
        result = self.engine.analyze(
            stock_code='000001',
            stock_name='某股票',
            financial_data=None,
            red_flag_data=None,
            mda_data=None,
            announcement_data=None,
            governance_data=None,
        )
        
        # 应该返回默认结论
        self.assertIsNotNone(result.recommendation)
        self.assertLessEqual(result.confidence, 50)  # 缺失财务数据，置信度受限
    
    def test_batch_analyze(self):
        """测试批量分析"""
        stocks = [
            {
                'stock_code': '000001',
                'stock_name': '平安银行',
                'financial_data': {'roe': 12, 'revenue_growth': 8},
                'red_flag_data': {'score': 15, 'verdict': 'LOW'},
                'mda_data': {'strategic_themes': ['数字化'], 'risks': []},
                'announcement_data': {'sentiment_score': 0.3},
                'governance_data': {'score': 80},
            },
            {
                'stock_code': '000002',
                'stock_name': '万科A',
                'financial_data': {'roe': 5, 'revenue_growth': -5},
                'red_flag_data': {'score': 60, 'verdict': 'HIGH'},
                'mda_data': {'strategic_themes': [], 'risks': ['债务风险']},
                'announcement_data': {'sentiment_score': -0.5},
                'governance_data': {'score': 60},
            },
        ]
        
        results = self.engine.batch_analyze(stocks)
        
        self.assertEqual(len(results), 2)
        self.assertIsNotNone(results[0].recommendation)
        self.assertIsNotNone(results[1].recommendation)


class TestReportGenerator(unittest.TestCase):
    """测试报告生成器"""
    
    def setUp(self):
        from module8_investment_conclusion import InvestmentEngine, ReportGenerator
        self.engine = InvestmentEngine()
        self.generator = ReportGenerator()
    
    def test_generate_summary_report(self):
        """测试文本报告生成"""
        result = self.engine.analyze(
            stock_code='000858',
            stock_name='五粮液',
            financial_data={
                'roe': 15.5,
                'revenue_growth': 12.0,
                'net_profit_cash_ratio': 95,
                'gross_margin': 38,
                'debt_ratio': 35,
            },
            red_flag_data={'score': 10, 'verdict': 'LOW'},
            mda_data={
                'strategic_themes': ['数字化'],
                'business_strengths': ['品牌'],
                'risks': [],
            },
            announcement_data={'sentiment_score': 0.5},
            governance_data={'score': 85},
        )
        
        report = self.generator.generate_summary_report(result)
        
        self.assertIn('000858', report)
        self.assertIn(result.recommendation, report)
        self.assertIn('财务健康', report)
    
    def test_generate_radar_data(self):
        """测试雷达图数据生成"""
        result = self.engine.analyze(
            stock_code='000858',
            stock_name='五粮液',
            financial_data={'roe': 15},
            red_flag_data={'score': 10},
            mda_data={},
            announcement_data={},
            governance_data={'score': 80},
        )
        
        radar = self.generator.generate_radar_data(result)
        
        self.assertIn('dimensions', radar)
        self.assertEqual(len(radar['dimensions']), 5)
    
    def test_generate_comparison_table(self):
        """测试对比表格生成"""
        results = []
        for i in range(3):
            result = self.engine.analyze(
                stock_code=f'00000{i}',
                stock_name=f'股票{i}',
                financial_data={'roe': 15 - i*3},
                red_flag_data={'score': 10 + i*10},
                mda_data={},
                announcement_data={},
                governance_data={'score': 80 - i*10},
            )
            results.append(result)
        
        table = self.generator.generate_comparison_table(results)
        
        self.assertEqual(len(table), 3)
        self.assertIn('股票代码', table[0])
        self.assertIn('投资建议', table[0])


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_full_pipeline(self):
        """完整流程测试"""
        from module8_investment_conclusion import InvestmentEngine
        
        engine = InvestmentEngine()
        
        # 模拟完整数据输入
        result = engine.analyze(
            stock_code='000858',
            stock_name='五粮液',
            year=2024,
            financial_data={
                'roe': 18.5,
                'revenue_growth': 15.0,
                'net_profit_cash_ratio': 105,
                'gross_margin': 40,
                'debt_ratio': 30,
            },
            red_flag_data={
                'score': 5,
                'verdict': 'NONE',
                'red_flags': [],
            },
            mda_data={
                'strategic_themes': ['数字化转型', '品牌升级', '国际化'],
                'business_strengths': ['品牌优势', '渠道优势', '研发优势'],
                'risks': ['原材料价格波动'],
            },
            announcement_data={
                'sentiment_score': 0.7,
                'recent_count': 10,
            },
            governance_data={
                'score': 90,
                'grade': 'A',
            },
        )
        
        # 验证输出
        self.assertIsNotNone(result.recommendation)
        self.assertIsNotNone(result.confidence)
        self.assertIsNotNone(result.total_score)
        self.assertIsNotNone(result.scores)
        self.assertIsNotNone(result.summary)
        
        # 验证数据结构完整
        data = result.to_dict()
        self.assertIn('stock_code', data)
        self.assertIn('recommendation', data)
        self.assertIn('scores', data)
        
        print(f"\n集成测试结果:")
        print(f"  股票: {result.stock_code} {result.stock_name}")
        print(f"  建议: {result.recommendation}")
        print(f"  评分: {result.total_score}")
        print(f"  置信度: {result.confidence}%")


if __name__ == '__main__':
    unittest.main()
