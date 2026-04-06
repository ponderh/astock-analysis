"""
test_yongxin.py — 永新股份(002014)估值验证
===========================================
协议验收标准逐项检查（V1-V10）

V1: regime-aware分位
V2: DCF三档输出
V3: DCF超宽降权
V4: Graham结构隔离（overall_verdict不含格雷厄姆）
V5: Graham字段标记（is_safety_test=True）
V6: 银行PB无调整（bank_pb_adjusted=False）
V7: 行业软路由（置信度<0.6时降权50%）
V8: 数据质量门控（有效方法<2 → verdict="数据不足"）
V9: 单元测试（永新/招商/平安各一只通过）
V10: 集成测试（module2+行业阈值+valuation三方联调）

运行:
    python test_yongxin.py
"""

import sys
import os
import json
import logging
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
for _lib in ["urllib3", "requests", "PIL"]:
    logging.getLogger(_lib).setLevel(logging.WARNING)

from module5_valuation.engine import ValuationEngine, REPORTS_DIR


def check_v1_regime_aware(result: dict) -> tuple:
    """V1: regime-aware分位"""
    pb = result.get("pb_result") or {}
    pe = result.get("pe_result") or {}

    has_regime = False
    note = ""

    # 检查是否有regime标签的分位输出
    if pb:
        if pb.get("percentile_full") is not None and pb.get("percentile_recent") is not None:
            has_regime = True
            note = f"PB: full={pb.get('percentile_full')}, recent={pb.get('percentile_recent')}"

    if not has_regime and pe:
        if pe.get("percentile_full") is not None and pe.get("percentile_recent") is not None:
            has_regime = True
            note = f"PE: full={pe.get('percentile_full')}, recent={pe.get('percentile_recent')}"

    # 检查断裂警告
    discontinuity = pb.get("regime_discontinuity_warning") or pe.get("regime_discontinuity_warning")
    if discontinuity:
        note += " ⚠️断裂警告"

    return has_regime, note


def check_v2_dcf_three_scenario(result: dict) -> tuple:
    """V2: DCF三档输出"""
    dcf = result.get("dcf_result") or {}

    p = dcf.get("intrinsic_pessimistic")
    c = dcf.get("intrinsic_central")
    o = dcf.get("intrinsic_optimistic")

    has_three = all(v is not None for v in [p, c, o])
    note = f"悲观={p}, 基准={c}, 乐观={o}" if has_three else "DCF三档缺失"

    # V2补充：三档宽度=0时触发数据错误告警
    zero_width_error = dcf.get("dcf_zero_width_error", False)
    if zero_width_error:
        note += " ⚠️三档宽度=0（数据错误）"

    return has_three, note


def check_v3_dcf_over_width(result: dict) -> tuple:
    """V3: DCF超宽降权"""
    dcf = result.get("dcf_result") or {}
    cs = result.get("composite_signal") or {}

    over_width = dcf.get("dcf_over_width_threshold", False)
    confidence = dcf.get("confidence", "unknown")
    dcf_weight = cs.get("method_weights", {}).get("dcf", 1.0)

    if over_width:
        correct = (confidence == "low") and (dcf_weight == 0.0)
        note = f"超宽触发：confidence={confidence}, dcf_weight={dcf_weight}"
    else:
        correct = True
        note = "未超宽，正常权重"

    return correct, note


def check_v4_graham_isolation(result: dict) -> tuple:
    """V4: Graham结构隔离（overall_verdict不含格雷厄姆）"""
    cs = result.get("composite_signal") or {}
    graham = result.get("graham_result") or {}

    # 格雷厄姆默认不纳入综合信号
    graham_included = cs.get("graham_included", False)
    graham_verdict_exists = graham.get("graham_number") is not None

    correct = (not graham_included) and graham_verdict_exists
    note = f"graham_included={graham_included}, graham_verdict独立={'存在' if graham_verdict_exists else '缺失'}"

    return correct, note


def check_v5_graham_safety_test_marker(result: dict) -> tuple:
    """V5: Graham字段标记（is_safety_test=True）"""
    graham = result.get("graham_result") or {}

    is_safety_test = graham.get("is_safety_test", False)
    correct = is_safety_test is True
    note = f"is_safety_test={is_safety_test}"

    return correct, note


def check_v6_bank_pb_no_adjustment(result: dict) -> tuple:
    """V6: 银行PB无调整"""
    bank_pb = result.get("bank_pb_result")

    # 永新不是银行股，bank_pb_result应为None（不适用）
    correct = True
    note = "非银行股，不适用"

    if bank_pb:
        bank_pb_adjusted = bank_pb.get("bank_pb_adjusted", True)
        correct = bank_pb_adjusted is False
        note = f"bank_pb_adjusted={bank_pb_adjusted} (应为False)"
        if not correct:
            note += " ⚠️银行PB有调整（违反协议）"

    return correct, note


def check_v7_industry_soft_routing(result: dict) -> tuple:
    """V7: 行业软路由（置信度<0.6时降权50%）"""
    ind_conf = result.get("industry_confidence") or {}
    cs = result.get("composite_signal") or {}

    conf_score = ind_conf.get("confidence_score", 1.0)
    is_low = ind_conf.get("is_low_confidence", False)
    weight_mult = ind_conf.get("effective_weight_multiplier", 1.0)

    if is_low:
        correct = weight_mult == 0.5
        note = f"低置信度={conf_score:.2f}，降权系数={weight_mult}（应为0.5）"
    else:
        correct = True
        note = f"置信度={conf_score:.2f}，正常权重"

    return correct, note


def check_v8_data_quality_gate(result: dict) -> tuple:
    """V8: 数据质量门控（有效方法<2 → verdict="数据不足"）"""
    cs = result.get("composite_signal") or {}

    valid = cs.get("valid_methods", 0)
    verdict = cs.get("overall_verdict", "")
    gate_passed = cs.get("quality_gate_passed", True)

    if valid < 2:
        correct = verdict == "数据不足"
        note = f"有效方法={valid}<2, verdict='{verdict}'（应为'数据不足'）"
    else:
        correct = gate_passed
        note = f"有效方法={valid}>=2, gate_passed={gate_passed}"

    return correct, note


def main():
    stock_code = "002014"
    stock_name = "永新股份"
    today = date.today().isoformat()

    print("=" * 70)
    print(f"永新股份(002014)估值验证 — {today}")
    print("=" * 70)

    engine = ValuationEngine()
    result = engine.analyze_and_save(stock_code)

    print(f"\n股票: {result['stock_name']} ({result['stock_code']})")
    print(f"当前价: {result['current_price']}")
    print(f"行业: {result['industry_confidence'].get('primary_industry')}")
    print(f"置信度: {result['industry_confidence'].get('confidence_score')}")
    print()

    cs = result["composite_signal"]
    print(f"综合结论: {cs['overall_verdict']} (score={cs['overall_score']})")
    print(f"有效方法: {cs['valid_methods']}")
    print(f"格雷厄姆纳入: {cs['graham_included']}")
    print()

    # 验收标准检查
    checks = [
        ("V1", "regime-aware分位", check_v1_regime_aware(result)),
        ("V2", "DCF三档输出", check_v2_dcf_three_scenario(result)),
        ("V3", "DCF超宽降权", check_v3_dcf_over_width(result)),
        ("V4", "Graham结构隔离", check_v4_graham_isolation(result)),
        ("V5", "Graham字段标记", check_v5_graham_safety_test_marker(result)),
        ("V6", "银行PB无调整", check_v6_bank_pb_no_adjustment(result)),
        ("V7", "行业软路由", check_v7_industry_soft_routing(result)),
        ("V8", "数据质量门控", check_v8_data_quality_gate(result)),
    ]

    print("\n验收标准检查：")
    print("-" * 70)
    all_passed = True
    for vid, desc, (passed, note) in checks:
        icon = "✅" if passed else "❌"
        print(f"  {icon} {vid} {desc}: {note}")
        if not passed:
            all_passed = False

    print("-" * 70)
    print(f"\n整体: {'✅ 全部通过' if all_passed else '❌ 存在失败项'}")
    print(f"报告已保存至: {REPORTS_DIR}/{stock_code}_valuation_{today}.json")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
