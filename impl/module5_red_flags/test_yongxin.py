#!/usr/bin/env python3
"""
test_yongxin.py — 永新股份(002014)红旗验证
==========================================
预期结果:
  verdict = "通过" 或 "存疑"（MEDIUM_PLEDGE触发黄旗，但整体质量好）
  overall_score ≥ 70
  red_flags = [] (无红色)
  extreme_flags = 0

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

from module5_red_flags.engine import RedFlagEngine, REPORTS_DIR


def main():
    stock_code = "002014"
    stock_name = "永新股份"
    today = date.today().isoformat()

    print("=" * 70)
    print(f"永新股份(002014)红旗验证 — {today}")
    print("=" * 70)

    engine = RedFlagEngine(mda_enabled=False)
    report = engine.analyze_and_save(stock_code)

    print("\n" + report.summary())

    # 验证
    passed = True
    checks = []

    # 检查1: verdict ∈ {"通过", "存疑"}（永新健康，但20%质押触发黄旗）
    checks.append(("verdict ∈ {通过, 存疑}", report.verdict in {"通过", "存疑"}, report.verdict))

    # 检查2: overall_score >= 70
    checks.append(("overall_score >= 70", report.overall_score >= 70, f"{report.overall_score}"))

    # 检查3: extreme_flags == 0
    checks.append(("无极端红旗", len(report.extreme_flags) == 0, f"{len(report.extreme_flags)}个"))

    # 检查4: red_flags应为空（无红色）
    checks.append(("red_flags == 0", len(report.red_flags) == 0, f"{len(report.red_flags)}个"))

    # 检查5: governance signal 正常
    gov = report.governance
    checks.append(("pledge_ratio <= 30%", gov.pledge_ratio <= 30.0, f"{gov.pledge_ratio:.1f}%"))
    checks.append(("audit_score == 0", gov.audit_score == 0, f"{gov.audit_score}"))
    checks.append(("goodwill_pct <= 5%", gov.goodwill_pct <= 5.0, f"{gov.goodwill_pct:.1f}%"))

    # 检查6: financial health
    fin = report.financial
    if fin.roe_latest is not None:
        checks.append(("ROE >= 10%", fin.roe_latest >= 10.0, f"{fin.roe_latest:.1f}%"))

    print("\n" + "=" * 70)
    print("验证结果:")
    print("=" * 70)

    all_passed = True
    for desc, result, value in checks:
        icon = "✅" if result else "❌"
        status = "PASS" if result else "FAIL"
        print(f"  {icon} [{status}] {desc}: {value}")
        if not result:
            all_passed = False

    print("=" * 70)
    if all_passed:
        print("✅ 永新股份验证通过!")
    else:
        print("❌ 永新股份验证未通过")
    print("=" * 70)

    report_file = REPORTS_DIR / f"{stock_code}_{today}.json"
    print(f"\n报告已保存: {report_file}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
