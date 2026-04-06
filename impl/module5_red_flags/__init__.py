"""
module5_red_flags: 财务红旗引擎
==============================
核心串联模块，整合模块2+模块6+模块7+模块9+行业阈值库
"""

from .engine import RedFlagEngine, analyze
from .scorer import (
    RedFlagScorer,
    RedFlag,
    GovernanceBlock,
    FinancialBlock,
    IndustryThresholdBlock,
    MDABlock,
    AnnouncementBlock,
    ScoredReport,
)
from .api import screen, screen_batch, load_report, list_reports, set_stock_name

__all__ = [
    "RedFlagEngine",
    "RedFlagScorer",
    "analyze",
    "screen",
    "screen_batch",
    "load_report",
    "list_reports",
    "set_stock_name",
    "RedFlag",
    "GovernanceBlock",
    "FinancialBlock",
    "IndustryThresholdBlock",
    "MDABlock",
    "AnnouncementBlock",
    "ScoredReport",
]
