"""
股权质押追踪
============
数据源：akshare stock_gpzy_pledge_ratio_em（东方财富/同花顺）
企查查：仅作补充，不阻塞主流程

数据优势：
- stock_gpzy_pledge_ratio_em 按交易日期返回全市场质押比例
- 每行一只股票，包含"质押比例"(%)列
- 2024-09-30最新数据覆盖A股全量股票
"""

from typing import Tuple
import pandas as pd

try:
    import akshare as ak
    AKSHARE_OK = True
except ImportError:
    AKSHARE_OK = False


# 质押比例阈值（与screen.py保持一致：<25%正常，25-50%偏高，>50%高危）
NORMAL_THRESHOLD = 25.0    # < 25% 正常
ELEVATED_THRESHOLD = 50.0  # 25-50% 偏高
HIGH_THRESHOLD = 999.0

# 质押比例数据默认使用日期（可配置）
# 建议使用最新可用季度末日期，如 20240930（2024Q3）
# 可通过环境变量 GOVERNANCE_PLEDGE_DATE 或 EquityPledgeFetcher(primary_date="YYYYMMDD") 覆盖
import os as _os
PRIMARY_DATE = _os.environ.get("GOVERNANCE_PLEDGE_DATE", "20240930")


def _signal_from_ratio(ratio: float) -> str:
    if ratio < NORMAL_THRESHOLD:
        return "正常"
    elif ratio < ELEVATED_THRESHOLD:
        return "偏高"
    else:
        return "高危"


class EquityPledgeFetcher:
    """股权质押数据获取器（东方财富数据源）"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._cache: dict = {}  # 简单内存缓存 (date -> DataFrame)

    def get_pledge_ratio(self, stock_code: str) -> Tuple[float, str]:
        """
        获取公司最新的股权质押比例

        Returns
        -------
        (pledge_ratio_pct: float, signal: str)
            pledge_ratio_pct: 质押比例(%)
            signal: 正常 / 偏高 / 高危
        """
        if not AKSHARE_OK:
            return 0.0, "数据源不可用(akshare未安装)"

        code6d = stock_code.zfill(6)

        ratio = self._get_ratio_from_date(code6d, PRIMARY_DATE)
        if ratio is not None:
            return ratio, _signal_from_ratio(ratio)
        # 不在列表中 = 无质押记录（比例为0）
        return 0.0, "正常(无质押记录或已退市)"

    def _get_ratio_from_date(self, code6d: str, date: str) -> float | None:
        """从指定日期的数据中查找目标股票的质押比例"""
        # 使用缓存
        if date in self._cache:
            df = self._cache[date]
        else:
            try:
                df = ak.stock_gpzy_pledge_ratio_em(date=date)
                self._cache[date] = df
            except Exception:
                self._cache[date] = None
                return None

        if df is None or df.empty:
            return None

        # 精确匹配股票代码
        mask = df["股票代码"].astype(str).str.strip() == code6d
        if mask.any():
            return float(df.loc[mask, "质押比例"].iloc[0])
        return None

    def get_pledge_detail(self, stock_code: str, date: str = "20240930") -> pd.DataFrame:
        """
        获取公司在指定日期的质押详情

        Returns
        -------
        DataFrame with key columns
        """
        if not AKSHARE_OK:
            return pd.DataFrame()

        code6d = stock_code.zfill(6)

        if date not in self._cache:
            try:
                self._cache[date] = ak.stock_gpzy_pledge_ratio_em(date=date)
            except Exception:
                return pd.DataFrame()

        df = self._cache[date]
        if df is None or df.empty:
            return pd.DataFrame()

        mask = df["股票代码"].astype(str).str.strip() == code6d
        if not mask.any():
            return pd.DataFrame()

        cols = ["股票代码", "股票简称", "交易日期", "所属行业",
                "质押比例", "质押股数", "质押市值", "质押笔数"]
        avail = [c for c in cols if c in df.columns]
        return df.loc[mask, avail].reset_index(drop=True)
