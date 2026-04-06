#!/usr/bin/env python3
"""
test_kangmei.py — 康美药业(600518)红旗验证
===========================================
预期结果:
  verdict = "高风险" ✅（已知问题公司，审计非标）
  触发 ≥ 1 个 EXTREME 红旗 ✅（AUDIT_NON_STANDARD: 2018-2021审计非标）
  audit_score >= 1 ✅（审计意见非标）
  overall_score <= 70（因AUDIT_NON_STANDARD扣30分）

注: 康美药业已退市(破产重整)，部分API数据不可用
      核心红旗来自module9的KNOWN_HIGH_RISK标注+审计历史非标

运行:
  python test_kangmei.py
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
    stock_code = "600518"
    stock_name = "康美药业"
    today = date.today().isoformat()

    print("=" * 70)
    print(f"康美药业(600518)红旗验证 — {today}")
    print("=" * 70)

    engine = RedFlagEngine(mda_enabled=False)
    report = engine.analyze_and_save(stock_code)

    print("\n" + report.summary())

    # 验证
    checks = []

    # 检查1: verdict = "高风险"
    checks.append(("verdict == '高风险'", report.verdict == "高风险", report.verdict))

    # 检查2: extreme_flags >= 1（康美2018-2021审计非标）
    checks.append(("有极端红旗(≥1)", len(report.extreme_flags) >= 1, f"{len(report.extreme_flags)}个"))

    # 检查3: audit_score >= 1（康美有审计非标）
    checks.append(("audit_score >= 1", report.governance.audit_score >= 1, f"{report.governance.audit_score}"))

    # 检查4: 总红旗数（red+yellow+extreme）>= 1（至少1个极端红旗）
    total_flags = len(report.red_flags) + len(report.yellow_flags) + len(report.extreme_flags)
    checks.append(("红旗总数 >= 1", total_flags >= 1, f"{total_flags}个"))

    # 检查5: overall_score <= 70（因AUDIT_NON_STANDARD扣30分）
    checks.append(("overall_score <= 70", report.overall_score <= 70, f"{report.overall_score}"))

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

    # 详细列出所有红旗
    print("\n触发红旗详情:")
    for f in report.extreme_flags:
        print(f"  🔴 [极] {f.code}: {f.label} — {f.detail}")
    for f in report.red_flags:
        print(f"  🔴 [红] {f.code}: {f.label} — {f.detail}")
    for f in report.yellow_flags:
        print(f"  🟡 [黄] {f.code}: {f.label} — {f.detail}")

    # 审计意见详情
    print(f"\n审计意见历史: {report.governance.audit_opinions}")

    print("=" * 70)
    if all_passed:
        print("✅ 康美药业验证通过!")
    else:
        print("❌ 康美药业验证未通过")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
