"""
combos.py: 三大危险信号组合逻辑
==============================

三种组合红旗：
1. cfo_ar_combo: 净现比<0.8 + 应收增速>营收增速（连续2年）
2. double_surge: 存货+应收账款双激增
3. margin_up_inventory_down: 毛利率升+周转降

这些组合比单一指标更能揭示财务问题。
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

# 三大危险信号定义
COMBO_FLAGS = {
    "cfo_ar_combo": {
        "name": "现金流恶化+应收异常",
        "description": "净现比<0.8(连续2年) + 应收增速>营收增速×1.3(连续2年)",
        "conditions": [
            "net_cash_ratio_ltm < 0.8 连续2年",
            "receivable_growth > revenue_growth × 1.3 连续2年"
        ],
        "severity": "RED",
        "weight": 4,
        "module": "模块3/4: 盈利质量",
    },
    "double_surge": {
        "name": "存货+应收账款双激增",
        "description": "存货增速>营收增速+15% 且 应收增速>营收增速+20%",
        "conditions": [
            "inventory_growth > revenue_growth + 0.15",
            "receivable_growth > revenue_growth + 0.20"
        ],
        "severity": "RED",
        "weight": 3,
        "module": "模块3/4: 盈利质量",
    },
    "margin_up_inventory_down": {
        "name": "毛利率升+周转降",
        "description": "毛利率提升>3pct 但 周转天数下降>15%",
        "conditions": [
            "gross_margin_change > 0.03",
            "turnover_days_change < -0.15"
        ],
        "severity": "RED",
        "weight": 4,
        "module": "模块3/4: 盈利质量",
        "verification_required": True,
    }
}


def check_cfo_ar_combo(df: pd.DataFrame) -> Dict:
    """
    检验 cfo_ar_combo：净现比<0.8 + 应收增速>营收增速（连续2年）
    =========================================================================

    Returns
    -------
    Dict with keys: triggered(bool), years(list of str), net_cash_ratio(list),
                    ar_to_rev_growth_diff(list), severity
    """
    required = ['statDate', 'net_cash_ratio', 'receivable_growth', 'revenue_growth']
    if not all(c in df.columns for c in required):
        return {"triggered": False, "reason": "缺少必要列"}

    # 取最近4年（有连续2年数据即可）
    df_sorted = df.sort_values('statDate').tail(4)

    # 连续2年净现比<0.8
    ncr_cols = df_sorted[['statDate', 'net_cash_ratio']].dropna()
    if len(ncr_cols) < 2:
        return {"triggered": False, "reason": "净现比数据不足"}

    cfo_bad_years = []
    for _, r in ncr_cols.iterrows():
        if r['net_cash_ratio'] < 0.8:
            cfo_bad_years.append(str(r['statDate']))

    # 连续2年应收增速>营收增速×1.3
    ar_cols = df_sorted[['statDate', 'receivable_growth', 'revenue_growth']].dropna()
    if len(ar_cols) < 2:
        ar_triggered = False
        ar_years = []
    else:
        ar_years = []
        for _, r in ar_cols.iterrows():
            rev_g = r.get('revenue_growth', 0)
            if pd.notna(rev_g) and rev_g > 0 and pd.notna(r.get('receivable_growth')):
                if r['receivable_growth'] > rev_g * 1.3:
                    ar_years.append(str(r['statDate']))
        ar_triggered = len(ar_years) >= 2

    # 两者都触发才算组合触发
    cfo_triggered = len(cfo_bad_years) >= 2
    triggered = cfo_triggered and ar_triggered

    return {
        "triggered": triggered,
        "cfo_triggered": cfo_triggered,
        "ar_triggered": ar_triggered,
        "cfo_bad_years": cfo_bad_years[-2:] if cfo_bad_years else [],
        "ar_surge_years": ar_years[-2:] if ar_years else [],
        "severity": "RED" if triggered else ("YELLOW" if (cfo_triggered or ar_triggered) else "GREEN"),
        "combo_name": COMBO_FLAGS["cfo_ar_combo"]["name"],
    }


def check_double_surge(df: pd.DataFrame) -> Dict:
    """
    检验 double_surge：存货+应收账款双激增
    """
    required = ['revenue_growth', 'receivable_growth']
    # inventory_growth may not be available - use as optional
    if not all(c in df.columns for c in required):
        return {"triggered": False, "reason": "缺少revenue_growth或receivable_growth列"}

    df_sorted = df.sort_values('statDate').tail(2)  # 最近2年

    results = []
    for _, r in df_sorted.iterrows():
        rev_g = r.get('revenue_growth', 0)
        if pd.isna(rev_g) or rev_g <= 0:
            results.append(False)
            continue

        ar_g = r.get('receivable_growth', 0)
        inv_g = r.get('inventory_growth', 0)

        # 如果缺少存货数据，只检查应收
        if pd.isna(inv_g):
            results.append(not pd.isna(ar_g) and ar_g > rev_g + 0.20)
        else:
            results.append(
                (inv_g > rev_g + 0.15) and
                (not pd.isna(ar_g) and ar_g > rev_g + 0.20)
            )

    triggered = len(results) >= 2 and all(results)

    return {
        "triggered": triggered,
        "inv_surge": not pd.isna(df_sorted['inventory_growth'].iloc[-1]) if 'inventory_growth' in df_sorted.columns else None,
        "ar_surge": not pd.isna(df_sorted['receivable_growth'].iloc[-1]) if 'receivable_growth' in df_sorted.columns else None,
        "revenue_growth_latest": df_sorted['revenue_growth'].iloc[-1] if 'revenue_growth' in df_sorted.columns else None,
        "severity": "RED" if triggered else "GREEN",
        "combo_name": COMBO_FLAGS["double_surge"]["name"],
    }


def check_margin_up_inventory_down(df: pd.DataFrame) -> Dict:
    """
    检验 margin_up_inventory_down：毛利率升+周转降
    """
    required = ['gross_margin', 'receivable_days']
    if not all(c in df.columns for c in required):
        return {"triggered": False, "reason": "缺少gross_margin或receivable_days列"}

    df_sorted = df.sort_values('statDate').tail(2)
    if len(df_sorted) < 2:
        return {"triggered": False, "reason": "数据不足2年"}

    latest = df_sorted.iloc[-1]
    prev = df_sorted.iloc[0]

    gm_change = latest.get('gross_margin', 0) - prev.get('gross_margin', 0)
    td_change = (latest.get('receivable_days', 0) - prev.get('receivable_days', 0)) / prev.get('receivable_days', 1)

    triggered = (gm_change > 0.03) and (td_change < -0.15)

    return {
        "triggered": triggered,
        "gross_margin_change": gm_change,
        "turnover_days_change_pct": td_change,
        "severity": "RED" if triggered else "GREEN",
        "combo_name": COMBO_FLAGS["margin_up_inventory_down"]["name"],
        "verification_required": True,
    }


def check_all_combos(df: pd.DataFrame) -> List[Dict]:
    """
    运行所有三大危险信号组合检验
    ==============================
    """
    results = []

    for combo_id, combo_def in COMBO_FLAGS.items():
        if combo_id == "cfo_ar_combo":
            result = check_cfo_ar_combo(df)
        elif combo_id == "double_surge":
            result = check_double_surge(df)
        elif combo_id == "margin_up_inventory_down":
            result = check_margin_up_inventory_down(df)
        else:
            continue

        results.append({
            "combo_id": combo_id,
            "name": combo_def["name"],
            "severity": combo_def["severity"],
            "weight": combo_def["weight"],
            "module": combo_def["module"],
            **result
        })

    return results


def check_combo_flags(df: pd.DataFrame) -> Dict:
    """
    汇总三大危险信号检验结果
    ========================
    """
    all_results = check_all_combos(df)
    red_count = sum(1 for r in all_results if r.get("severity") == "RED")

    return {
        "total_combos": len(all_results),
        "red_count": red_count,
        "yellow_count": sum(1 for r in all_results if r.get("severity") == "YELLOW"),
        "overall_severity": "RED" if red_count >= 2 else ("YELLOW" if red_count == 1 else "GREEN"),
        "details": all_results,
    }
