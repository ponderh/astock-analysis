"""
test_pingan.py — 中国平安(601318)估值验证
==========================================
验证多业务加权（软路由）：平安=70%非银金融+20%银行+10%房地产

运行:
    python test_pingan.py
"""

import sys
import os
import logging
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
for _lib in ["urllib3", "requests"]:
    logging.getLogger(_lib).setLevel(logging.WARNING)

from module5_valuation.engine import ValuationEngine, REPORTS_DIR


def main():
    stock_code = "601318"
    stock_name = "中国平安"
    today = date.today().isoformat()

    print("=" * 70)
    print(f"中国平安(601318)估值验证 — {today}")
    print("=" * 70)

    engine = ValuationEngine()
    result = engine.analyze_and_save(stock_code)

    print(f"\n股票: {result['stock_name']} ({result['stock_code']})")
    print(f"当前价: {result['current_price']}")

    # 行业置信度
    ind_conf = result.get("industry_confidence") or {}
    print(f"\n行业置信度:")
    print(f"  主行业: {ind_conf.get('primary_industry')}")
    print(f"  置信度: {ind_conf.get('confidence_score')}")
    print(f"  主营构成: {ind_conf.get('business_mix')}")
    print(f"  路由方法: {ind_conf.get('routing_method')}")
    print(f"  is_low_confidence: {ind_conf.get('is_low_confidence')}")
    print(f"  降权系数: {ind_conf.get('effective_weight_multiplier')}")

    # Graham
    graham = result.get("graham_result") or {}
    print(f"\n格雷厄姆数:")
    print(f"  graham_number: {graham.get('graham_number')}")
    print(f"  is_safety_test: {graham.get('is_safety_test')} ← 必须为True")
    print(f"  verdict: {graham.get('verdict')}")
    print(f"  included_in_overall: {graham.get('included_in_overall')} ← 必须为False")

    # 综合
    cs = result["composite_signal"]
    print(f"\n综合结论: {cs['overall_verdict']} (score={cs['overall_score']})")
    print(f"有效方法: {cs['valid_methods']}")

    # 检查点
    checks = {
        "V4 Graham隔离": graham.get("included_in_overall") is False,
        "V5 is_safety_test": graham.get("is_safety_test") is True,
        "V7 软路由": ind_conf.get("confidence_score") is not None,
    }

    print("\n关键检查:")
    all_pass = True
    for name, passed in checks.items():
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}")
        if not passed:
            all_pass = False

    print(f"\n{'✅ 全部通过' if all_pass else '❌ 存在失败项'}")
    print(f"报告已保存至: {REPORTS_DIR}/{stock_code}_valuation_{today}.json")

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
