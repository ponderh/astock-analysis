"""
regime_classifier.py: 制度Regime分类器
=======================================
根据年份和重大制度事件为数据打regime标签。

Regime体系：
  - pre-split-share: 2005-09-30前（股权分置改革前）
  - post-split-share: 2005-09-30至2019-12-31（股权分置改革后至注册制前）
  - post-full-circulation: 2020年后，全流通逐步实现
  - registration-system: 2020年后，注册制全面推行（默认使用）

协议要求：
  1. 数据必须打regime标签
  2. 默认使用 registration-system（2020+）后数据
  3. 历史分位必须使用regime-aware计算
"""

from __future__ import annotations
from datetime import date, datetime
from typing import Optional, Tuple, List
from enum import Enum


class Regime(Enum):
    """制度 Regime：标注数据所属的资本市场制度阶段"""
    PRE_SPLIT_SHARE = "pre-split-share"
    POST_SPLIT_SHARE = "post-split-share"
    POST_FULL_CIRCULATION = "post-full-circulation"
    REGISTRATION_SYSTEM = "registration-system"

    @classmethod
    def default(cls) -> "Regime":
        return cls.REGISTRATION_SYSTEM

    @classmethod
    def from_year(cls, year: int) -> "Regime":
        if year < 2005:
            return cls.PRE_SPLIT_SHARE
        elif year < 2020:
            return cls.POST_SPLIT_SHARE
        else:
            return cls.REGISTRATION_SYSTEM

    def is_recent(self) -> bool:
        return self in (self.POST_FULL_CIRCULATION, self.REGISTRATION_SYSTEM)


# ============================================================
# 关键制度时间节点
# ============================================================

# 股权分置改革启动（试点）
SPLIT_SHARE_REFORM_START = date(2005, 5, 9)

# 股权分置改革基本完成（大部分股票获得流通权）
SPLIT_SHARE_REFORM_COMPLETE = date(2006, 9, 30)

# 创业板注册制正式推出
GEM_REGISTRATION = date(2020, 8, 24)

# 科创板注册制正式推出
STAR_MARKET_REGISTRATION = date(2019, 7, 22)

# 注册制全面推行（主板也实行注册制改革）
FULL_REGISTRATION_SYSTEM = date(2024, 1, 1)  # 预估，主板注册制改革时间


# ============================================================
# Regime 分类函数
# ============================================================

def classify_date(d: date) -> Regime:
    """
    根据日期判断所属regime

    Parameters
    ----------
    d : date
        数据日期

    Returns
    -------
    Regime
    """
    if d < SPLIT_SHARE_REFORM_START:
        return Regime.PRE_SPLIT_SHARE
    elif d < date(2020, 1, 1):
        return Regime.POST_SPLIT_SHARE
    else:
        return Regime.REGISTRATION_SYSTEM


def classify_year(year: int) -> Regime:
    """根据年份判断regime（用于财务数据年份分类）"""
    if year < 2005:
        return Regime.PRE_SPLIT_SHARE
    elif year < 2020:
        return Regime.POST_SPLIT_SHARE
    else:
        return Regime.REGISTRATION_SYSTEM


def is_recent_regime(d: date) -> bool:
    """判断是否为近regime（用于默认数据筛选）"""
    return d >= date(2020, 1, 1)


def get_regime_range(regime: Regime) -> Tuple[date, date]:
    """
    获取指定regime的时间范围

    Returns
    -------
    (start_date, end_date)
    """
    if regime == Regime.PRE_SPLIT_SHARE:
        return (date(1990, 12, 19), SPLIT_SHARE_REFORM_START)
    elif regime == Regime.POST_SPLIT_SHARE:
        return (SPLIT_SHARE_REFORM_COMPLETE, date(2019, 12, 31))
    elif regime == Regime.POST_FULL_CIRCULATION:
        return (date(2020, 1, 1), date(2024, 12, 31))
    elif regime == Regime.REGISTRATION_SYSTEM:
        return (GEM_REGISTRATION, date.today())
    else:
        return (date(2020, 1, 1), date.today())


def regime_label_for_year(year: int) -> str:
    """返回年份的regime标签字符串（用于输出）"""
    return classify_year(year).value


# ============================================================
# Regime-aware 数据过滤
# ============================================================

def filter_by_regime(
    df,
    date_column: str = "statDate",
    use_recent_only: bool = False,
) -> Tuple:
    """
    按regime过滤数据DataFrame

    Parameters
    ----------
    df : pd.DataFrame
        包含日期列的DataFrame
    date_column : str
        日期列名
    use_recent_only : bool
        是否只使用注册制后数据（默认True，符合协议）

    Returns
    -------
    (full_df, recent_df)
        full_df: 全量数据（含regime标签）
        recent_df: 注册制后数据（use_recent_only=True时）
    """
    import pandas as pd

    if df.empty:
        return df, df

    # 转换日期
    if date_column in df.columns:
        df = df.copy()
        # 支持多种日期格式
        try:
            df["_regime_date"] = pd.to_datetime(df[date_column], errors="coerce").dt.date
        except Exception:
            df["_regime_date"] = None

        # 打regime标签
        def get_regime(d):
            if d is None:
                return Regime.REGISTRATION_SYSTEM.value
            try:
                if isinstance(d, str):
                    d = date.fromisoformat(d[:10])
                return classify_date(d).value
            except Exception:
                return Regime.REGISTRATION_SYSTEM.value

        df["regime"] = df["_regime_date"].apply(get_regime)

        # 筛选近regime（2020+）
        recent = df[df["_regime_date"] >= date(2020, 1, 1)] if use_recent_only else df

        return df, recent
    else:
        return df, df


# ============================================================
# 注册制后年份列表（用于计算）
# ============================================================

def get_registration_years() -> List[int]:
    """返回注册制后的年份列表（2020年至今）"""
    current_year = date.today().year
    return list(range(2020, current_year + 1))


# ============================================================
# 注册制前后数据量检测
# ============================================================

def check_regime_discontinuity(
    full_n: int,
    recent_n: int,
    threshold_pct: float = 20.0,
) -> Tuple[bool, float]:
    """
    检测regime断裂（数据分布差异）

    Parameters
    ----------
    full_n : int
        全量数据样本数
    recent_n : int
        注册制后数据样本数
    threshold_pct : float
        断裂阈值（默认20%）

    Returns
    -------
    (is_discontinuous, discontinuity_pct)
    """
    if full_n == 0:
        return False, 0.0

    discontinuity_pct = abs(full_n - recent_n) / full_n * 100
    is_discontinuous = discontinuity_pct > threshold_pct

    return is_discontinuous, discontinuity_pct


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    test_dates = [
        date(2004, 1, 1),
        date(2007, 6, 1),
        date(2015, 1, 1),
        date(2021, 3, 15),
        date(2023, 12, 31),
    ]

    for d in test_dates:
        r = classify_date(d)
        print(f"{d} → {r.value}")

    print("\n注册制年份:", get_registration_years())
    print("断裂检测:", check_regime_discontinuity(100, 75))
