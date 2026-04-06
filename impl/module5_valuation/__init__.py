"""
module5_valuation: A股估值分析引擎
===================================
符合P1-1协议约束的估值分析模块。

核心原则：
  1. PB是A股主估值锚，PE为辅
  2. DCF是范围估计工具（非点估计），必须输出三档
  3. 格雷厄姆数是安全边际测试（is_safety_test=True），默认排除出综合信号
  4. 行业路由是软置信度，禁止硬拦截
  5. 历史分位必须打regime标签，默认使用注册制后数据

快速使用：
    from module5_valuation.api import analyze
    result = analyze("002014", "永新股份")
"""

from .engine import ValuationEngine, analyze, STOCK_NAMES
from .models import (
    Regime,
    Confidence,
    Verdict,
    IndustryConfidence,
    PercentileResult,
    DCFResult,
    GrahamResult,
    BankPBResult,
    CompositeSignal,
    ValuationBlock,
)

__all__ = [
    # 引擎
    "ValuationEngine",
    "analyze",
    "STOCK_NAMES",
    # 数据模型
    "Regime",
    "Confidence",
    "Verdict",
    "IndustryConfidence",
    "PercentileResult",
    "DCFResult",
    "GrahamResult",
    "BankPBResult",
    "CompositeSignal",
    "ValuationBlock",
]
