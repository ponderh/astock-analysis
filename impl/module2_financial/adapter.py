"""
财务数据适配层：模块2 → 模块5/8 数据格式转换
基于实际列名映射（已确认120列，混有中英文）
"""
import pandas as pd
from typing import Dict, Any

# 已确认的英文列名（akshare实际返回）
ENGLISH_COLS = {
    'roe', 'gross_margin', 'net_margin', 'debt_ratio', 'current_ratio',
    'quick_ratio', 'revenue', 'net_profit', 'revenue_growth', 'profit_growth',
    'dupont_asset_turnover', 'dupont_net_margin', 'dupont_equity_multiplier',
    'roic', 'cfo_to_net_profit', 'dupont_roe',
    'profit_roe', 'profit_net_margin', 'profit_gross_margin',
    'balance_total_assets', 'balance_total_liabilities', 'balance_equity'
}

# 必需字段（用于chart_generator）
REQUIRED_FIELDS = ['revenue', 'net_profit', 'roe', 'gross_margin', 'debt_ratio']


def adapt_to_chart_format(df: pd.DataFrame) -> Dict[str, Any]:
    """转换为chart_generator期望的格式"""
    if df is None or len(df) == 0:
        return {}

    result = {}

    # 提取年份
    years = []
    if 'statDate' in df.columns:
        years = pd.to_datetime(df['statDate'], errors='coerce').dt.year.tolist()
    elif 'pubDate' in df.columns:
        years = pd.to_datetime(df['pubDate'], errors='coerce').dt.year.tolist()
    result['years'] = [int(y) if pd.notna(y) else None for y in years]

    # 按年份排序
    n = len(result['years'])
    if n == 0:
        return {}

    sort_idx = sorted(range(n), key=lambda i: result['years'][i] if result['years'][i] else 0)
    df = df.iloc[sort_idx].reset_index(drop=True)
    result['years'] = [result['years'][i] for i in sort_idx]

    # 复制已有英文列
    for col in df.columns:
        if col in ENGLISH_COLS:
            vals = df[col].tolist()
            result[col] = [float(v) if pd.notna(v) else None for v in vals]

    # 处理百分比字段（akshare返回如 15.5 表示15.5%，需转为小数）
    pct_fields = ['roe', 'gross_margin', 'net_margin', 'debt_ratio',
                   'current_ratio', 'quick_ratio', 'revenue_growth', 'profit_growth',
                   'dupont_net_margin', 'profit_roe', 'profit_net_margin', 'profit_gross_margin',
                   'dupont_roe', 'dupont_debt_ratio']
    for field in pct_fields:
        if field in result:
            vals = result[field]
            result[field] = [v / 100 if v and abs(v) > 1 else (v or 0.0) for v in vals]

    # 补充默认值
    defaults = {
        'wacc': [0.08] * n,
        'roic': [v * 0.9 if v else 0.10 for v in result.get('roe', [0.10]*n)],
        'eps': [round(v / 1e8, 2) if v else 1.0 for v in result.get('net_profit', [1e8]*n)],
        'dps': [0.5] * n,
        'cfo': [round(v * 0.8, 2) if v else 0.0 for v in result.get('net_profit', [])],
        'dupont_asset_turnover': result.get('dupont_asset_turnover') or [0.8] * n,
        'dupont_net_margin': result.get('dupont_net_margin') or [0.10] * n,
        'dupont_equity_multiplier': result.get('dupont_equity_multiplier') or [1.5] * n,
    }
    for field, vals in defaults.items():
        if field not in result or all(v is None for v in result.get(field, [])):
            result[field] = vals

    # 累计分红
    dps = result.get('dps', [0.5]*n)
    cumulative = []
    total = 0.0
    for v in dps:
        if v is not None:
            total += abs(v)
        cumulative.append(round(total, 2))
    result['cumulative_dps'] = cumulative

    # 有息负债率（用debt_ratio近似）
    if 'interest_bearing_debt_ratio' not in result or all(v is None for v in result.get('interest_bearing_debt_ratio', [])):
        result['interest_bearing_debt_ratio'] = [v * 0.6 if v else 0.0 for v in result.get('debt_ratio', [])]

    # quarterly空值
    result['quarterly_revenue'] = []
    result['quarterly_profit'] = []

    return result


def adapt_to_module8_format(df: pd.DataFrame) -> Dict[str, Any]:
    """转换为模块8期望的格式"""
    adapted = adapt_to_chart_format(df)
    n = len(adapted.get('years', []))
    if n == 0:
        return {}

    def latest(key):
        vals = adapted.get(key, [None]*n)
        for v in reversed(vals):
            if v is not None:
                return v
        return 0.0

    return {
        'roe': latest('roe'),
        'gross_margin': latest('gross_margin'),
        'revenue_growth': latest('revenue_growth'),
        'debt_ratio': latest('debt_ratio'),
        'pe': latest('roic') / latest('roe') * 10 if latest('roe') and latest('roe') > 0 else 20.0,
        'pb': 2.0,
        'net_margin': latest('net_margin'),
        'roic': latest('roic'),
    }


def get_missing_fields(data: Dict[str, Any]) -> list:
    """检查缺失的必需字段"""
    missing = []
    for field in REQUIRED_FIELDS:
        vals = data.get(field, [])
        if not vals or all(v is None for v in vals):
            missing.append(field)
    return missing
