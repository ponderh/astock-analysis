"""
test_zhaoshang.py — 招商银行(600036)估值验证
============================================
V6: 银行PB无调整（bank_pb_adjusted=False）

运行:
    python test_zhaoshang.py
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
    stock_code = "600036"
    stock_name = "招商银行"
    today = date.today().isoformat()

    print("=" * 70)
    print(f"招商银行(600036)估值验证 — {today}")
    print("=" * 70)

    engine = ValuationEngine()
    result = engine.analyze_and_save(stock_code)

    print(f"\n股票: {result['stock_name']} ({result['stock_code']})")
    print(f"当前价: {result['current_price']}")

    cs = result["composite_signal"]
    print(f"\n综合结论: {cs['overall_verdict']} (score={cs['overall_score']})")

    # 银行PB检查
    bank_pb = result.get("bank_pb_result")
    print(f"\n银行PB结果:")
    if bank_pb:
        print(f"  current_pb: {bank_pb.get('current_pb')}")
        print(f"  industry_avg_pb: {bank_pb.get('industry_avg_pb')}")
        print(f"  vs_industry_pct: {bank_pb.get('vs_industry_pct')}%")
        print(f"  verdict: {bank_pb.get('verdict')}")
        print(f"  bank_pb_adjusted: {bank_pb.get('bank_pb_adjusted')} ← 必须是False")
        print(f"  note: {bank_pb.get('note')}")

        v6_pass = bank_pb.get("bank_pb_adjusted") is False
    else:
        print("  bank_pb_result为None")
        v6_pass = False

    print(f"\nV6 银行PB无调整: {'✅ PASS' if v6_pass else '❌ FAIL'}")
    print(f"报告已保存至: {REPORTS_DIR}/{stock_code}_valuation_{today}.json")

    return v6_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
