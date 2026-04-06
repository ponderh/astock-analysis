"""
industry_thresholds: 行业阈值数据库
===================================
目标：
- 用akshare全量数据计算申万一级行业（28个）的各指标分位数
- 实现 get_threshold / get_red_flags API
- 实现三大危险信号组合逻辑

三级降级：精确（SW3）→ 二级（SW2） → 一级（SW1） → 全市场
"""

from .fetcher import IndustryThresholdFetcher
from .api import (
    get_threshold,
    get_red_flags,
    check_combo_flags,
    get_industry_class,
    list_sw1_industries,
    list_indicators,
)
from .combos import COMBO_FLAGS, check_all_combos

__all__ = [
    "IndustryThresholdFetcher",
    "get_threshold",
    "get_red_flags",
    "check_combo_flags",
    "check_all_combos",
    "get_industry_class",
    "COMBO_FLAGS",
]
