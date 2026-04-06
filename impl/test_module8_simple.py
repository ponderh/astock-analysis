#!/usr/bin/env python3
import sys, os
sys.path.insert(0, '/home/ponder/.openclaw/workspace/astock-implementation/impl/module8_investment_conclusion')

# Patch relative imports
import config
import scoring_model
import aggregator
import investment_engine

engine = investment_engine.InvestmentEngine()
result = engine.analyze('000858', {
    'financial': {'roe': 0.25, 'gross_margin': 0.72, 'revenue_growth': 0.10},
    'red_flags': {'red': 0, 'yellow': 0, 'extreme': 0},
    'mda': {'strategic_commitments': 4, 'risk_factors': 2},
    'governance': {'equity_pledge_ratio': 0.05}
})
print(f"Rating: {result.get('rating')}")
print(f"Score: {result.get('overall_score')}")
print(f"Confidence: {result.get('confidence')}")
