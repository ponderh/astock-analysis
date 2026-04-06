#!/usr/bin/env python3
"""模块8分析入口"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import scoring_model
import aggregator
import investment_engine
import report_generator

def analyze(stock_code: str, combined_data: dict) -> dict:
    engine = investment_engine.InvestmentEngine()
    return engine.analyze(stock_code, combined_data)

if __name__ == '__main__':
    result = analyze('000858', {
        'financial': {'roe': 0.25, 'gross_margin': 0.72, 'revenue_growth': 0.10, 'debt_ratio': 0.25},
        'red_flags': {'red': 0, 'yellow': 0, 'extreme': 0},
        'mda': {'strategic_commitments': 4, 'risk_factors': 2},
        'governance': {'equity_pledge_ratio': 0.05}
    })
    print(f"Rating: {result.get('rating')}")
    print(f"Score: {result.get('overall_score')}")
