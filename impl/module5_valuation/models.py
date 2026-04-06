"""
models.py: 估值分析引擎 — 数据模型
=====================================
定义估值分析所需的所有数据结构，符合P1-1协议约束：

1. PB是A股主估值锚，PE为辅
2. DCF是范围估计工具（非点估计），必须输出三档
3. 格雷厄姆数是安全边际测试（is_safety_test=True），默认排除出综合信号
4. 行业路由是软置信度，禁止硬拦截
5. 历史分位必须打regime标签

Regime标签体系:
  - pre-split-share: 股权分置改革前（2005-09-30前）
  - post-split-share: 股权分置改革后（2005-09-30至2019-12-31）
  - post-full-circulation: 全流通时代（2020-01-01至注册制全面推行）
  - registration-system: 注册制时代（2020年之后，默认使用）

质量门控红线：
  - DCF输出单点估计 → 禁止上线
  - 格雷厄姆数进入综合信号默认权重 → 禁止上线
  - 银行PB含任何调整参数 → 禁止上线
  - 历史分位无regime标签 → 禁止上线
  - 行业硬路由 → 禁止上线
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Literal
from enum import Enum
import math


# ============================================================
# Regime 枚举
# ============================================================

class Regime(Enum):
    """制度 Regime：标注数据所属的资本市场制度阶段"""
    PRE_SPLIT_SHARE = "pre-split-share"        # 股权分置改革前
    POST_SPLIT_SHARE = "post-split-share"      # 股权分置改革后
    POST_FULL_CIRCULATION = "post-full-circulation"  # 全流通时代
    REGISTRATION_SYSTEM = "registration-system"  # 注册制时代（默认）

    @classmethod
    def default(cls) -> "Regime":
        return cls.REGISTRATION_SYSTEM

    @classmethod
    def from_year(cls, year: int) -> "Regime":
        """根据年份推断regime"""
        if year < 2005:
            return cls.PRE_SPLIT_SHARE
        elif year < 2020:
            return cls.POST_SPLIT_SHARE
        else:
            return cls.REGISTRATION_SYSTEM

    def is_recent(self) -> bool:
        """是否为近regime（用于默认数据选择）"""
        return self in (self.POST_FULL_CIRCULATION, self.REGISTRATION_SYSTEM)


# ============================================================
# 置信度枚举
# ============================================================

class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============================================================
# Verdict 枚举
# ============================================================

class Verdict(Enum):
    UNDERVALUED = "低估"
    FAIR_VALUE = "合理"
    OVERVALUED = "高估"
    INSUFFICIENT_DATA = "数据不足"
    UNCERTAIN = "不确定"


# ============================================================
# 行业置信度结果
# ============================================================

@dataclass
class IndustryConfidence:
    """
    行业置信度评分结果（软路由核心）
    =====================================
    协议要求：禁止硬路由，用置信度评分+多方法加权代替
    """
    stock_code: str
    primary_industry: str              # 申万一级行业
    confidence_score: float            # 0~1，主营构成置信度
    business_mix: Dict[str, float]     # {行业名: 主营占比}，来自主营构成
    sw3_industry: str = ""             # 申万三级行业（更精确）
    sw2_industry: str = ""             # 申万二级行业
    routing_method: str = "unknown"   # 路由方法：business_mix / single / fallback
    is_low_confidence: bool = False    # < 0.6 时为True，降权50%

    def effective_weight_multiplier(self) -> float:
        """置信度降权系数：低置信度时所有行业调整结果降权50%"""
        if self.is_low_confidence:
            return 0.5
        return 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# PE/PB分位结果（regime-aware）
# ============================================================

@dataclass
class PercentileResult:
    """
    历史分位结果（regime-aware）
    ============================
    协议要求：
    1. 数据必须打regime标签
    2. 默认使用 registration-system（2020+）后数据
    3. 双窗口输出：percentile_full（全量）和 percentile_recent（注册制后）
    4. 差异 > 20% → regime_discontinuity_warning: true
    """
    # 指标值
    indicator: str           # "PE" 或 "PB"
    actual_value: float     # 当前实际值

    # 双窗口分位
    percentile_full: Optional[float] = None   # 全量数据分位（10年）
    percentile_recent: Optional[float] = None # 注册制后分位（2020+，默认）

    # Regime信息
    regime_full: str = "unknown"      # 全量数据的regime
    regime_recent: str = "unknown"     # 近regime标签
    regime_discontinuity_warning: bool = False  # 差异>20%触发

    # 分位阈值
    threshold_p20: Optional[float] = None  # P20低估阈值（行业）
    threshold_p80: Optional[float] = None  # P80高估阈值（行业）

    # 置信度
    confidence: str = "low"
    data_years: int = 0              # 有效数据年数
    n_stocks_used: int = 0           # 计算使用的股票数

    # 辅助信息
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def primary_percentile(self) -> Optional[float]:
        """返回近regime分位（默认使用）"""
        return self.percentile_recent if self.percentile_recent is not None else self.percentile_full

    def check_discontinuity(self) -> bool:
        """检查regime断裂并设置警告"""
        if self.percentile_full is not None and self.percentile_recent is not None:
            diff = abs(self.percentile_full - self.percentile_recent)
            if diff > 20.0:
                self.regime_discontinuity_warning = True
                return True
        return False


# ============================================================
# DCF三档结果
# ============================================================

@dataclass
class DCFResult:
    """
    DCF估值结果（三档，非点估计）
    ==============================
    协议要求：
    1. 必须输出三档：乐观/基准/悲观
    2. 三档宽度 > 当前股价50%时 → confidence=low，权重归零
    3. 三档宽度 = 0 时 → 数据错误告警
    """
    # 三档内在价值
    intrinsic_pessimistic: Optional[float] = None  # 悲观档（元/股）
    intrinsic_central: Optional[float] = None      # 基准档（元/股）
    intrinsic_optimistic: Optional[float] = None   # 乐观档（元/股）

    # 宽度分析
    confidence_width_pct: Optional[float] = None   # 三档宽度%（相对于中间值）
    dcf_over_width_threshold: bool = False         # 宽度>50%触发
    dcf_zero_width_error: bool = False             # 宽度=0（数据错误）

    # 置信度
    confidence: str = "low"                        # high/medium/low

    # 当前股价（用于宽度计算）
    current_price: Optional[float] = None

    # WACC参数
    wacc: Optional[float] = None
    perpetual_growth_rate: Optional[float] = None

    # 隐含误差
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def compute_width_pct(self) -> Optional[float]:
        """计算三档宽度%（相对于中间档）"""
        vals = [v for v in [self.intrinsic_pessimistic, self.intrinsic_central, self.intrinsic_optimistic] if v is not None]
        if len(vals) < 3:
            return None
        central = vals[1]
        if central == 0:
            self.dcf_zero_width_error = True
            return 0.0
        width = (vals[2] - vals[0]) / central * 100
        self.confidence_width_pct = width
        # 宽度>50% → 降权
        if width > 50.0:
            self.dcf_over_width_threshold = True
            self.confidence = "low"
        elif width > 30.0:
            self.confidence = "medium"
        else:
            self.confidence = "high"
        return width

    def effective_weight(self) -> float:
        """DCF有效权重（超宽时归零）"""
        if self.dcf_over_width_threshold:
            return 0.0
        if self.confidence == "low":
            return 0.0
        return 1.0  # 正常时≤20%，由engine控制


# ============================================================
# 格雷厄姆结果（安全测试，隔离输出）
# ============================================================

@dataclass
class GrahamResult:
    """
    格雷厄姆数结果（安全边际测试，非估值锚）
    =========================================
    协议要求：
    1. is_safety_test = True（明确这是安全测试，不是估值锚）
    2. verdict双轨：overall_verdict不含格雷厄姆，graham_verdict独立输出
    3. 综合信号权重 = 0（默认排除）
    """
    graham_number: Optional[float] = None   # 格雷厄姆数（元/股）
    is_safety_test: bool = True             # 固定为True，标记为安全测试

    # 与股价比较
    current_price: Optional[float] = None
    safety_margin_pct: Optional[float] = None  # (graham - price) / price * 100
    safety_passed: bool = False               # 价格 < 格雷厄姆数

    # 估值判断
    verdict: str = "不确定"                    # 独立格雷厄姆判断

    # 基础EPS和BPS
    eps_ttm: Optional[float] = None
    bps: Optional[float] = None

    # 版本标记（原版22.5系数）
    formula_version: str = "original_22.5"   # 不使用修正版

    # Graham数是否进入综合信号（默认False）
    included_in_overall: bool = False        # 结构性隔离

    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def compute_safety_margin(self) -> None:
        """计算安全边际"""
        if self.graham_number is not None and self.current_price is not None and self.current_price > 0:
            self.safety_margin_pct = (self.graham_number - self.current_price) / self.current_price * 100
            self.safety_passed = self.current_price < self.graham_number


# ============================================================
# 银行PB结果（Phase1无调整）
# ============================================================

@dataclass
class BankPBResult:
    """
    银行PB结果（Phase1无调整版）
    =============================
    协议要求：
    1. 仅输出原始PB与行业均值的比较
    2. 不引入任何不良率/拨备覆盖率调整
    3. 明确标注：bank_pb_adjusted = False
    """
    current_pb: Optional[float] = None      # 原始PB
    industry_avg_pb: Optional[float] = None # 银行行业平均PB

    # 比较结果
    vs_industry_pct: Optional[float] = None  # (current - industry_avg) / industry_avg * 100

    # 估值判断
    verdict: str = "不确定"
    confidence: str = "low"

    # 标注Phase1
    bank_pb_adjusted: bool = False            # 固定False，Phase1不做调整
    note: str = "Phase1不含信用风险调整"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def compute_vs_industry(self) -> None:
        """计算相对行业均值"""
        if self.current_pb is not None and self.industry_avg_pb is not None and self.industry_avg_pb != 0:
            self.vs_industry_pct = (self.current_pb - self.industry_avg_pb) / self.industry_avg_pb * 100


# ============================================================
# 综合信号结果
# ============================================================

@dataclass
class CompositeSignal:
    """
    综合信号（格雷厄姆默认排除）
    ============================
    协议要求：格雷厄姆数默认权重=0，不进入综合信号
    """
    # 综合verdict（格雷厄姆默认排除）
    overall_verdict: str = "不确定"
    overall_score: float = 50.0   # 0-100

    # 各方法贡献分（已降权）
    pe_pb_score: float = 0.0      # PE/PB分位贡献
    dcf_score: float = 0.0        # DCF三档贡献
    bank_pb_score: float = 0.0   # 银行PB贡献

    # 有效方法数
    valid_methods: int = 0        # 有效方法<2 → verdict="数据不足"
    method_weights: Dict[str, float] = field(default_factory=dict)  # 各方法权重

    # 数据质量
    data_source: str = "unknown"  # 数据来源标记
    regime_discontinuity_warning: bool = False

    # 格雷厄姆独立信号（双轨之一）
    graham_verdict: str = "不确定"
    graham_included: bool = False  # 是否手动纳入综合信号（默认False）

    # 最低数据质量门控
    quality_gate_passed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def apply_quality_gate(self) -> None:
        """数据质量门控：有效方法<2 → verdict="数据不足" """
        if self.valid_methods < 2:
            self.overall_verdict = "数据不足"
            self.overall_score = 0.0
            self.quality_gate_passed = False


# ============================================================
# 估值报告（最终输出）
# ============================================================

@dataclass
class ValuationBlock:
    """
    估值分析完整报告
    =================
    整合所有估值方法输出，按协议要求组织
    """
    stock_code: str
    stock_name: str
    report_date: str

    # 当前价格
    current_price: Optional[float] = None

    # 行业信息（软路由）
    industry_confidence: Optional[IndustryConfidence] = None

    # 分位结果（regime-aware）
    pe_result: Optional[PercentileResult] = None
    pb_result: Optional[PercentileResult] = None

    # DCF三档
    dcf_result: Optional[DCFResult] = None

    # 格雷厄姆（安全测试，隔离）
    graham_result: Optional[GrahamResult] = None

    # 银行PB（无调整）
    bank_pb_result: Optional[BankPBResult] = None

    # 综合信号（格雷厄姆默认排除）
    composite_signal: CompositeSignal = field(default_factory=CompositeSignal)

    # 原始财务数据（用于计算）
    _financial_data: Dict[str, Any] = field(default_factory=dict, repr=False)

    # 数据来源
    data_source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "report_date": self.report_date,
            "current_price": self.current_price,
            "industry_confidence": self.industry_confidence.to_dict() if self.industry_confidence else None,
            "pe_result": self.pe_result.to_dict() if self.pe_result else None,
            "pb_result": self.pb_result.to_dict() if self.pb_result else None,
            "dcf_result": self.dcf_result.to_dict() if self.dcf_result else None,
            "graham_result": self.graham_result.to_dict() if self.graham_result else None,
            "bank_pb_result": self.bank_pb_result.to_dict() if self.bank_pb_result else None,
            "composite_signal": self.composite_signal.to_dict(),
            "data_source": self.data_source,
        }
        return result

    def summary(self) -> str:
        """人类可读摘要"""
        cs = self.composite_signal
        lines = [
            f"📊 估值分析 {self.stock_code} {self.stock_name} — {self.report_date}",
            f"  当前价: {self.current_price}",
            f"  综合结论: {cs.overall_verdict} (score={cs.overall_score:.0f}/100)",
            f"  PE分位: {self.pe_result.primary_percentile() if self.pe_result else 'N/A'}%",
            f"  PB分位: {self.pb_result.primary_percentile() if self.pb_result else 'N/A'}%",
        ]
        if self.dcf_result:
            d = self.dcf_result
            lines.append(f"  DCF: 悲观={d.intrinsic_pessimistic} 基准={d.intrinsic_central} 乐观={d.intrinsic_optimistic} (置信度={d.confidence})")
        if self.graham_result:
            g = self.graham_result
            lines.append(f"  格雷厄姆: {g.graham_number} (安全测试,is_safety_test={g.is_safety_test})")
        if self.bank_pb_result:
            b = self.bank_pb_result
            lines.append(f"  银行PB: {b.current_pb} vs行业均值{b.industry_avg_pb} (调整={b.bank_pb_adjusted})")
        lines.append(f"  格雷厄姆纳入综合: {self.composite_signal.graham_included} (默认=False)")
        return "\n".join(lines)
