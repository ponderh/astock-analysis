"""
商誉/并购监控
==============
数据源：akshare stock_financial_abstract（THS同花顺财务摘要）

商誉/净资产比例判断：
- < 10%：正常
- 10-30%：偏高（存在并购溢价风险）
- > 30%：高危（减值风险大，曾有公司一次性全额计提）

商誉减值风险信号：
- 商誉绝对值 > 10亿 且 商誉/净资产 > 20%
- 连续2年以上商誉/净资产比例上升
"""

from typing import Tuple
import pandas as pd

try:
    import akshare as ak
    AKSHARE_OK = True
except ImportError:
    AKSHARE_OK = False


NORMAL_THRESHOLD = 10.0    # < 10%
ELEVATED_THRESHOLD = 30.0  # 10-30%
HIGH_THRESHOLD = 999.0    # > 30%


def _parse_yuan(val) -> float:
    """将数值或文本转换为元"""
    if pd.isna(val) or val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _signal_from_ratio(ratio: float) -> str:
    if ratio < NORMAL_THRESHOLD:
        return "正常"
    elif ratio < ELEVATED_THRESHOLD:
        return "偏高"
    else:
        return "高危"


class GoodwillFetcher:
    """商誉数据获取器"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def get_goodwill_ratio(self, stock_code: str) -> Tuple[float, float, float, str]:
        """
        获取最新一期的商誉/净资产比例

        Returns
        -------
        (goodwill_yuan: float, net_assets_yuan: float, ratio_pct: float, signal: str)
            goodwill_yuan: 商誉（元）
            net_assets_yuan: 净资产（元）
            ratio_pct: 商誉/净资产比例（%）
            signal: 正常 / 偏高 / 高危
        """
        if not AKSHARE_OK:
            return 0.0, 0.0, 0.0, "数据源不可用(akshare未安装)"

        try:
            df = ak.stock_financial_abstract(symbol=stock_code)
        except Exception as e:
            return 0.0, 0.0, 0.0, f"获取失败:{type(e).__name__}"

        if df is None or df.empty:
            return 0.0, 0.0, 0.0, "数据为空"

        # 找商誉行和净资产行
        gw_mask = df["指标"] == "商誉"
        na_mask = df["指标"] == "股东权益合计(净资产)"

        goodwill = 0.0
        net_assets = 0.0

        if gw_mask.any():
            row = df[gw_mask].iloc[0]
            # 找最新一列（有数据的）
            for col in df.columns[2:]:  # 前两列是选项/指标
                val = row[col]
                v = _parse_yuan(val)
                if v != 0.0:
                    goodwill = v
                    break

        if na_mask.any():
            row = df[na_mask].iloc[0]
            for col in df.columns[2:]:
                val = row[col]
                v = _parse_yuan(val)
                if v != 0.0:
                    net_assets = v
                    break

        if net_assets == 0.0:
            return goodwill, 0.0, 0.0, "净资产数据不可用"

        ratio_pct = (goodwill / net_assets) * 100.0
        signal = _signal_from_ratio(ratio_pct)

        return goodwill, net_assets, ratio_pct, signal

    def get_goodwill_history(self, stock_code: str, years: int = 5) -> pd.DataFrame:
        """
        获取近N年的商誉/净资产比例变化

        Returns
        -------
        DataFrame with columns: 报告期, 商誉(元), 净资产(元), 比例(%)
        """
        if not AKSHARE_OK:
            return pd.DataFrame()

        try:
            df = ak.stock_financial_abstract(symbol=stock_code)
        except Exception:
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        gw_mask = df["指标"] == "商誉"
        na_mask = df["指标"] == "股东权益合计(净资产)"

        if not (gw_mask.any() and na_mask.any()):
            return pd.DataFrame()

        gw_row = df[gw_mask].iloc[0]
        na_row = df[na_mask].iloc[0]

        records = []
        for col in df.columns[2:]:
            gw_val = _parse_yuan(gw_row[col])
            na_val = _parse_yuan(na_row[col])
            if na_val != 0.0:
                records.append({
                    "报告期": col,
                    "商誉(元)": gw_val,
                    "净资产(元)": na_val,
                    "比例(%)": round((gw_val / na_val) * 100.0, 4),
                })

        result = pd.DataFrame(records)
        if not result.empty:
            # 按日期排序
            result = result.sort_values("报告期", ascending=False).reset_index(drop=True)
        return result

    def detect_impairment_risk(self, stock_code: str) -> Tuple[bool, str]:
        """
        检测商誉减值风险

        Returns
        (has_risk: bool, reason: str)
        """
        history = self.get_goodwill_history(stock_code, years=3)
        if history.empty:
            return False, "无历史数据"

        latest = history.iloc[0]
        ratio = latest["比例(%)"]
        gw = latest["商誉(元)"]

        # 风险条件
        risk_signals = []

        if ratio > 30.0:
            risk_signals.append(f"商誉/净资产比例{ratio:.1f}%超过30%高危线")

        if gw > 10e8 and ratio > 20.0:
            risk_signals.append(f"商誉绝对值{gw/1e8:.1f}亿且比例{ratio:.1f}%偏高")

        # 检查比例是否连续上升
        if len(history) >= 2:
            history_sorted = history.sort_values("报告期")
            ratios = history_sorted["比例(%)"].tolist()
            if all(ratios[i] <= ratios[i+1] for i in range(len(ratios)-1)):
                if ratios[-1] > 10.0:
                    risk_signals.append(f"商誉比例连续{len(ratios)}期上升至{ratios[-1]:.1f}%")

        if risk_signals:
            return True, "; ".join(risk_signals)
        return False, "未检测到明显减值风险"
