"""
calculator.py: 财务指标计算引擎
==============================
实现：ROIC计算、杜邦分解、现金流分析、净现比
无前视偏差：所有计算使用当期数据
"""

from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

# WACC假设（无风险利率2.8% + 市场风险溢价5%，beta=1.0）
DEFAULT_WACC = 0.085


def calc_roic(
    operating_income: float,
    tax_rate: float,
    total_assets: float,
    current_liabilities: float,
    equity: float,
) -> float:
    """
    计算ROIC = NOPAT / Invested Capital
    =====================================

    ROIC = EBIT × (1 - Tax Rate) / (债务 + 股权 - 现金)

    Parameters
    ----------
    operating_income : float
        营业利润（EBIT近似）
    tax_rate : float
        实际税率 = 所得税/营业利润
    total_assets : float
        总资产
    current_liabilities : float
        流动负债（不含有息负债）
    equity : float
        股东权益

    Returns
    -------
    float
        ROIC（年化），超出[-2, 2]范围则截断
    """
    if total_assets <= 0 or equity <= 0:
        return np.nan

    # 有息负债 = 总资产 - 股东权益 - 流动无息负债（近似）
    # 用流动负债代替全部无息负债
    interest_bearing_debt = max(0, total_assets - equity - current_liabilities)
    invested_capital = interest_bearing_debt + equity

    if invested_capital <= 0:
        return np.nan

    nopat = operating_income * (1 - tax_rate)
    roic = nopat / invested_capital
    return float(np.clip(roic, -2, 2))


def dupont_decompose(roe: float) -> Dict[str, float]:
    """
    杜邦分解：ROE = 净利率 × 资产周转率 × 权益乘数
    ==============================================

    三因子贡献拆解：
    - 净利率因子 = net_profit / revenue
    - 周转率因子 = revenue / total_assets
    - 杠杆因子 = total_assets / equity

    Returns
    -------
    Dict
        {factor_name: contribution_to_roe}
    """
    return {
        "roe": roe,
        "net_margin_contrib": np.nan,      # 待外部数据填充
        "asset_turnover_contrib": np.nan,  # 待外部数据填充
        "leverage_contrib": np.nan,         # 待外部数据填充
        "note": "需同时传入revenue/total_assets/equity才能计算三因子贡献"
    }


def dupont_from_components(
    net_profit: float,
    revenue: float,
    total_assets: float,
    equity: float,
) -> Dict[str, float]:
    """
    完整杜邦分解（已知利润表和资产负债表时）
    ======================================
    """
    if revenue <= 0 or total_assets <= 0 or equity <= 0:
        return {"roe": np.nan}

    net_margin = net_profit / revenue
    asset_turnover = revenue / total_assets
    equity_multiplier = total_assets / equity

    roe = net_margin * asset_turnover * equity_multiplier

    return {
        "roe": float(roe),
        "net_margin": float(net_margin),
        "asset_turnover": float(asset_turnover),
        "equity_multiplier": float(equity_multiplier),
        # 三因子对ROE的贡献（乘法分解）
        "net_margin_contrib": float(net_margin),
        "asset_turnover_contrib": float(asset_turnover),
        "leverage_contrib": float(equity_multiplier),
        "note": "三因子相乘=ROE"
    }


def cashflow_analysis(
    operating_cf: float,
    net_profit: float,
    investing_cf: Optional[float] = None,
    financing_cf: Optional[float] = None,
) -> Dict[str, float]:
    """
    现金流分析
    ==========

    Parameters
    ----------
    operating_cf : float
        经营活动现金流量净额
    net_profit : float
        净利润
    investing_cf : float, optional
        投资活动现金流量净额
    financing_cf : float, optional
        筹资活动现金流量净额

    Returns
    -------
    Dict
        {
            net_cash_ratio: 净现比（经营CF/净利润）
            cfo_quality: 现金流质量评级（good/normal/poor）
            investing_ratio: 投资支出/经营CF比例
            financing_ratio: 筹资/经营CF比例
        }
    """
    result = {}

    # 净现比
    if net_profit != 0 and not np.isnan(net_profit):
        net_cash_ratio = operating_cf / net_profit
        result["net_cash_ratio"] = float(np.clip(net_cash_ratio, -5, 5))
    else:
        result["net_cash_ratio"] = np.nan

    # 现金流质量评级
    ncr = result.get("net_cash_ratio", np.nan)
    if np.isnan(ncr):
        result["cfo_quality"] = "unknown"
    elif ncr >= 0.8:
        result["cfo_quality"] = "good"
    elif ncr >= 0.5:
        result["cfo_quality"] = "normal"
    else:
        result["cfo_quality"] = "poor"

    # 投资支出/经营CF
    if investing_cf is not None and not np.isnan(investing_cf) and operating_cf != 0:
        result["investing_ratio"] = float(abs(investing_cf) / abs(operating_cf))
    else:
        result["investing_ratio"] = np.nan

    # 筹资/经营CF
    if financing_cf is not None and not np.isnan(financing_cf) and operating_cf != 0:
        result["financing_ratio"] = float(abs(financing_cf) / abs(operating_cf))
    else:
        result["financing_ratio"] = np.nan

    return result


def calc_net_cash_ratio(operating_cf: float, net_profit: float) -> float:
    """
    净现比 = 经营现金流/净利润
    用途：识别利润操纵/现金流恶化
    阈值：<0.8连续2年 → 危险信号
    """
    if net_profit == 0 or np.isnan(net_profit):
        return np.nan
    return float(np.clip(operating_cf / net_profit, -5, 5))


def calc_roic_simple(
    net_profit: float,
    total_assets: float,
    equity: float,
    current_liabilities: float = 0,
    tax_rate: float = 0.15,
) -> float:
    """
    简化ROIC估算（用净利润代替EBIT）
    ==============================

    当无法获取营业利润和税率时，用净利润近似：
    ROIC ≈ 净利润 / (总资产 - 流动负债)

    这是akshare指标中最接近ROIC的替代指标。
    """
    if total_assets <= 0:
        return np.nan
    ic = max(total_assets - current_liabilities, total_assets * 0.5)  # 至少用50%总资产作为IC
    if ic <= 0:
        return np.nan
    return float(np.clip(net_profit / ic, -2, 2))


def roe_vs_wacc(roe: float, wacc: float = DEFAULT_WACC) -> Dict[str, float]:
    """
    ROE vs WACC 对比
    ================
    返回差距和判断
    """
    spread = roe - wacc
    return {
        "roe": roe,
        "wacc": wacc,
        "spread": float(spread),
        "value_creating": spread > 0,
        "grade": "A" if spread > 0.05 else ("B" if spread > 0 else ("C" if spread > -0.05 else "D"))
    }


def assess_cfo_quality(net_cash_ratio: float, years: int = 2) -> str:
    """
    现金流质量评估
    ==============

    规则：
    - 净现比 >= 0.8: good
    - 净现比 0.5-0.8: normal
    - 净现比 < 0.5: poor（连续2年需警示）
    """
    if np.isnan(net_cash_ratio):
        return "unknown"
    if net_cash_ratio >= 0.8:
        return "good"
    elif net_cash_ratio >= 0.5:
        return "normal"
    else:
        return "poor"


def compute_all_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    对包含标准列的DataFrame计算所有指标
    ==================================

    标准输入列：revenue, net_profit, total_assets, equity,
                operating_cf, investing_cf, financing_cf,
                current_liabilities, roe (已有)

    输出：添加 roic, dupont_*, cfo_metrics 等列

    [FIX G2-3] ROIC优先用calc_roic（标准版），缺少operating_income/tax_rate时降级到calc_roic_simple
    """
    df = df.copy()

    # ROIC：优先标准版 calc_roic，降级到 calc_roic_simple
    has_full_data = all(col in df.columns for col in
                        ['operating_income', 'tax', 'total_assets', 'equity', 'current_liabilities'])
    has_simple_data = all(col in df.columns for col in
                          ['net_profit', 'total_assets', 'equity', 'current_liabilities'])

    if has_full_data:
        # [FIX G2-3] 优先使用标准ROIC（需营业利润和税率）
        df['roic'] = df.apply(
            lambda r: calc_roic(
                r.get('operating_income', 0),
                r.get('tax', 0),
                r.get('total_assets', 0),
                r.get('current_liabilities', 0),
                r.get('equity', 0),
            ) if pd.notna(r.get('total_assets')) else np.nan,
            axis=1
        )
    elif has_simple_data:
        # 降级到简化版（用净利润代替EBIT，假设税率15%）
        df['roic'] = df.apply(
            lambda r: calc_roic_simple(
                r.get('net_profit', 0),
                r.get('total_assets', 0),
                r.get('equity', 0),
                r.get('current_liabilities', 0),
            ) if pd.notna(r.get('total_assets')) else np.nan,
            axis=1
        )

    # 杜邦
    if all(col in df.columns for col in ['net_profit', 'revenue', 'total_assets', 'equity']):
        dupont_results = df.apply(
            lambda r: dupont_from_components(
                r.get('net_profit', 0),
                r.get('revenue', 0),
                r.get('total_assets', 0),
                r.get('equity', 0),
            ) if pd.notna(r.get('revenue')) else {},
            axis=1
        )
        dupont_df = pd.DataFrame(dupont_results.tolist())
        for col in ['net_margin', 'asset_turnover', 'equity_multiplier']:
            if col in dupont_df.columns:
                df[col] = dupont_df[col]

    # 现金流
    if 'operating_cf' in df.columns and 'net_profit' in df.columns:
        df['net_cash_ratio'] = df.apply(
            lambda r: calc_net_cash_ratio(
                r.get('operating_cf', 0), r.get('net_profit', 0)
            ) if pd.notna(r.get('net_profit')) else np.nan,
            axis=1
        )
        df['cfo_quality'] = df['net_cash_ratio'].apply(assess_cfo_quality)

    return df
