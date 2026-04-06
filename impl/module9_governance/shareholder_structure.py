"""
股权结构穿透
=============
数据源：akshare stock_circulate_stock_holder（THS同花顺）

功能：
1. 获取前10大股东及持股比例
2. 穿透识别实控人
3. 判断是否为"一股独大"或股权分散

实控人判断规则（优先级）：
1. 国资委/政府 → 实控人为"XX省国资委"
2. 境内/外法人持股最大者 → 实控人为该公司名
3. 自然人最大股东持股>30% → 实控人为该自然人
4. 多个法人持股相近（前两大股东持股差距<5%）→ 可能是无实控人/共同控制
"""

from typing import Tuple, List, Dict, Any
import pandas as pd

try:
    import akshare as ak
    AKSHARE_OK = True
except ImportError:
    AKSHARE_OK = False


# 实控人类型
CTRL_TYPE_STATE = "国有企业/国资委"
CTRL_TYPE_PE = "一般法人/PE"
CTRL_TYPE_NATURAL = "自然人"
CTRL_TYPE_UNKNOWN = "无法判断"


class ShareholderFetcher:
    """股东结构获取器"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def get_top_shareholders(self, stock_code: str, n: int = 10) -> pd.DataFrame:
        """
        获取前N大股东

        Returns
        -------
        DataFrame with columns: 股东名称, 持股数量, 占流通股比例, 股本性质
        """
        if not AKSHARE_OK:
            return pd.DataFrame()

        code6d = stock_code.zfill(6)
        try:
            df = ak.stock_circulate_stock_holder(symbol=code6d)
        except Exception:
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        # 取最新一期（第一行是最新的）
        latest_date = df.iloc[0]["截止日期"]
        latest = df[df["截止日期"] == latest_date].head(n).copy()
        return latest.reset_index(drop=True)

    def get_controller_info(self, stock_code: str) -> Tuple[float, str]:
        """
        获取实控人信息及持股比例

        Returns
        -------
        (controller_share_pct: float, controller_name: str)
        """
        top_df = self.get_top_shareholders(stock_code, n=10)
        if top_df.empty:
            return 0.0, "无法获取"

        # 确保持股比例列是数值型
        if "占流通股比例" in top_df.columns:
            ratio_col = "占流通股比例"
        else:
            return 0.0, "数据格式异常"

        top_df["_ratio_num"] = pd.to_numeric(top_df[ratio_col], errors="coerce").fillna(0)

        # 第一大股东
        largest = top_df.iloc[0]
        largest_share = float(largest["_ratio_num"])
        largest_name = str(largest["股东名称"])

        # 判断实控人类型
        ctrl_type, ctrl_name = self._identify_controller(top_df)

        return largest_share, f"{ctrl_name}({ctrl_type})"

    def _identify_controller(self, df: pd.DataFrame) -> Tuple[str, str]:
        """
        判断实控人类型和名称

        规则：
        1. 最大股东是"自然人"股本性质 → 实控人为该自然人
        2. 最大股东是"国有股"股本性质 → 国资企业
        3. 最大股东是法人（境内/境外）→ 一般法人/PE
        4. 政府关键词出现在最大股东名 → 国资
        """
        if df.empty:
            return CTRL_TYPE_UNKNOWN, "无数据"

        # 最大股东（已按比例降序排列）
        largest = df.iloc[0]
        name = str(largest.get("股东名称", ""))
        nature = str(largest.get("股本性质", ""))
        ratio = float(largest.get("_ratio_num", 0))

        # 自然人
        if "自然人" in nature:
            return CTRL_TYPE_NATURAL, name

        # 国有股
        if "国有" in nature:
            return CTRL_TYPE_STATE, name

        # 政府关键词
        state_keywords = ["国资委", "财政部", "人民政府", "中科院", "国有独资"]
        if any(kw in name for kw in state_keywords):
            return CTRL_TYPE_STATE, name

        # 境内/境外法人股
        if ratio > 5.0:  # 持股5%以上的主要法人
            return CTRL_TYPE_PE, name

        return CTRL_TYPE_PE, name

    def get_shareholder_structure_summary(self, stock_code: str) -> Dict[str, Any]:
        """
        获取股权结构摘要

        Returns
        -------
        {
            "top1_pct": float,       # 第一大股东持股%
            "top2_pct": float,       # 第二大股东持股%
            "top5_pct": float,       # 前五合计%
            "top10_pct": float,      # 前十合计%
            "controller_type": str,  # 实控人类型
            "controller_name": str,  # 实控人名称
            "is_concentrated": bool, # 是否一股独大(>50%为第一大股东)
        }
        """
        df = self.get_top_shareholders(stock_code, n=10)
        if df.empty:
            return {}

        df["_ratio_num"] = pd.to_numeric(df["占流通股比例"], errors="coerce").fillna(0)

        top1 = float(df.iloc[0]["_ratio_num"]) if len(df) >= 1 else 0.0
        top2 = float(df.iloc[1]["_ratio_num"]) if len(df) >= 2 else 0.0
        top5 = float(df["_ratio_num"].head(5).sum())
        top10 = float(df["_ratio_num"].sum())

        ctrl_type, ctrl_name = self._identify_controller(df)

        return {
            "top1_pct": top1,
            "top2_pct": top2,
            "top5_pct": top5,
            "top10_pct": top10,
            "controller_type": ctrl_type,
            "controller_name": ctrl_name,
            "is_concentrated": top1 > 50.0,
        }
