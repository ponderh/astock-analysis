"""
methods/: 估值方法集合
========================
每个方法独立实现，按协议约束输出标准化结果。
"""

from .pe_pb_percentile import get_pe_pb_percentile, get_current_pe_pb
from .dcf import compute_dcf_three_scenario, compute_dcf_implied_return
from .graham import analyze_graham, compute_graham_number, compute_safety_margin
from .bank_pb import analyze_bank_pb, is_bank_stock, should_use_bank_pb
from .industry_routing import get_industry_confidence, compute_industry_weighted_threshold

__all__ = [
    "get_pe_pb_percentile",
    "get_current_pe_pb",
    "compute_dcf_three_scenario",
    "compute_dcf_implied_return",
    "analyze_graham",
    "compute_graham_number",
    "compute_safety_margin",
    "analyze_bank_pb",
    "is_bank_stock",
    "should_use_bank_pb",
    "get_industry_confidence",
    "compute_industry_weighted_threshold",
]
