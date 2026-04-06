"""
FinancialFetcher: 财务数据获取器
===============================
- akshare为主数据源（有30秒超时保护）
- HDF5历史数据为辅助验证源（HDF5_only=True时跳过akshare）
- 自动处理上市不足10年的情况

HDF5匿名列映射（逆向推导，精确到小数点后6位验证）：
  profit:  code,pubDate,statDate, roe, net_margin, gross_margin, net_profit, tax, revenue, gross_profit, operating_profit
  balance: code,pubDate,statDate, total_assets, total_liab, equity, fixed_assets, current_assets, current_liabilities
  cashflow: code,pubDate,statDate, operating_cf, investing_cf, financing_cf, net_cash_change, ?, capex, dividend
  dupont:  code,pubDate,statDate, roe, asset_turnover, net_margin, equity_multiplier, debt_ratio, current_ratio, quick_ratio, cash_ratio
"""

import os
import signal
import warnings
from typing import Optional, Dict, List
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HDF5_FINANCIAL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "astock-strategy-v3", "data", "a_stock_financial.h5"
)

AKSHARE_TIMEOUT = 30


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("akshare fetch timed out")


# HDF5列名映射: {table_key: {f_index: standard_name}}
HDF5_COL_MAPS = {
    "balance": {
        3: "total_assets",
        4: "total_liabilities",
        5: "equity",
        6: "fixed_assets",
        7: "current_assets",
        8: "current_liabilities",
    },
    "cashflow": {
        # HDF5 cashflow表存储的是相对于净利润的比率，非绝对金额
        # 3: operating_cf/net_profit = 净现比 (f1 in raw = 0.609330)
        # 4: investing_cf/net_profit (f2)
        # 5: financing_cf/net_profit (f3)
        # 6: net_cash_change (f4, often NaN)
        # 7: capex/net_profit (f5)
        # 8: dividend/net_profit (f6=f7)
        3: "cfo_to_net_profit_ratio",  # 净现比 = 经营CF/净利润
        4: "investing_cf_ratio",
        5: "financing_cf_ratio",
        6: "net_cash_change",
        7: "capex_ratio",
        8: "dividend_ratio",
    },
    "dupont": {
        3: "roe",
        4: "asset_turnover",
        5: "net_margin",
        6: "equity_multiplier",
        7: "debt_ratio",
        8: "current_ratio",
        9: "quick_ratio",
        10: "cash_ratio",
    },
    "profit": {
        3: "roe",
        4: "net_margin",
        5: "gross_margin",
        6: "net_profit",
        7: "tax",
        8: "revenue",
        9: "gross_profit",
        10: "operating_profit",
    },
}


class FinancialFetcher:
    """财务数据获取器（akshare主 + HDF5辅）"""

    def __init__(self, hdf5_path: Optional[str] = None, timeout: int = AKSHARE_TIMEOUT,
                 hdf5_only: bool = False):
        self.timeout = timeout
        self.hdf5_path = hdf5_path or HDF5_FINANCIAL_PATH
        self.hdf5_only = hdf5_only
        self._ak = None

    def _get_ak(self):
        if self._ak is None:
            import akshare as ak
            self._ak = ak
        return self._ak

    def fetch(self, stock_code: str, years: int = 10) -> pd.DataFrame:
        """获取近N年财务数据，输出1行/年的干净DataFrame"""
        code_6d = self._normalize_code(stock_code)
        start_year = datetime.now().year - years

        df_h5 = self._fetch_hdf5_merged(code_6d)

        if self.hdf5_only:
            df_ak = pd.DataFrame()
        else:
            df_ak = self._fetch_akshare_safe(code_6d, start_year)

        df = self._merge_one_row_per_year(df_ak, df_h5)
        df = self._compute_metrics(df)
        df = self._annotate_gaap(df)
        return df.sort_values('statDate').reset_index(drop=True)

    def _fetch_akshare_safe(self, code_6d: str, start_year: int) -> pd.DataFrame:
        """akshare获取（30秒超时）"""
        try:
            ak = self._get_ak()
            old = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(self.timeout)
            try:
                df = ak.stock_financial_analysis_indicator(
                    symbol=code_6d, start_year=str(start_year)
                )
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old)
        except TimeoutError:
            warnings.warn(f"akshare timed out for {code_6d} — using HDF5 only")
            return pd.DataFrame()
        except Exception as e:
            warnings.warn(f"akshare error for {code_6d}: {e}")
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        col_map = self._detect_columns(df)
        df = df.rename(columns=col_map)
        if 'statDate' in df.columns:
            df = df[df['statDate'].astype(str).str.match(r'\d{4}-12-31', na=False)]
        df['data_source'] = 'akshare'
        return df

    def _detect_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        KNOWN = {
            '股票代码': 'code', 'code': 'code',
            '公告日期': 'pubDate', 'pub_date': 'pubDate',
            '日期': 'statDate', '报告日期': 'statDate', 'stat_date': 'statDate',
            '营业总收入': 'revenue', 'total_revenue': 'revenue',
            '净利润': 'net_profit', 'net_profit': 'net_profit',
            '资产总计': 'total_assets', 'total_assets': 'total_assets',
            '所有者权益合计': 'equity', 'total_equity': 'equity',
            '净资产收益率(ROE)': 'roe', '净资产收益率': 'roe', 'roe': 'roe',
            '销售毛利率': 'gross_margin', 'gross_margin': 'gross_margin',
            '销售净利率': 'net_margin', 'net_margin': 'net_margin',
            '经营活动产生的现金流量净额': 'operating_cf', 'operating_cf': 'operating_cf',
            '资产负债率': 'debt_ratio', 'debt_ratio': 'debt_ratio',
            '流动比率': 'current_ratio', '速动比率': 'quick_ratio',
            '存货周转天数': 'inventory_days',
            '应收账款周转天数': 'receivable_days',
            '应付账款周转天数': 'payable_days',
        }
        col_map = {}
        # 按长度降序排列，确保更具体的列名优先匹配
        sorted_known = sorted(KNOWN.items(), key=lambda x: len(x[0]), reverse=True)
        for col in df.columns:
            upper = str(col).upper()
            for known, target in sorted_known:
                # '日期' 只匹配报告日期，不匹配公告日期（公告日期单独处理）
                if col == '日期' and known == '公告日期':
                    continue
                if known.upper() in upper or upper in known.upper():
                    col_map[col] = target
                    break
        return col_map

    def _fetch_hdf5_merged(self, code_6d: str) -> pd.DataFrame:
        """HDF5获取并合并为1行/年"""
        if not os.path.exists(self.hdf5_path):
            return pd.DataFrame()

        try:
            code_pattern = f"sz.{code_6d}"
            table_data = {}  # key -> list of dicts

            for key in ['profit', 'balance', 'cashflow', 'dupont']:
                try:
                    df = pd.read_hdf(self.hdf5_path, key=key)
                    rows = df[df['code'] == code_pattern]
                    if rows.empty:
                        continue

                    col_map = HDF5_COL_MAPS.get(key, {})
                    records = []
                    for _, row in rows.iterrows():
                        rec = {'hdf5_key': key, 'statDate': str(row['statDate']), 'pubDate': str(row['pubDate'])}
                        for i, col in enumerate(df.columns):
                            if col in ('code', 'pubDate', 'statDate'):
                                continue
                            if i in col_map:
                                rec[col_map[i]] = row[col]
                            else:
                                rec[f'f{i}'] = row[col]
                        records.append(rec)
                    if records:
                        table_data[key] = records
                except Exception as e:
                    warnings.warn(f"HDF5 {key} failed: {e}")

            if not table_data:
                return pd.DataFrame()

            # Build one row per (statDate, hdf5_key), then merge by statDate
            all_records = []
            for key, records in table_data.items():
                all_records.extend(records)

            by_date = {}
            for rec in all_records:
                sd = rec['statDate']
                if sd not in by_date:
                    by_date[sd] = {}
                by_date[sd][rec['hdf5_key']] = rec

            merged = []
            for sd in sorted(by_date.keys()):
                entry = {'statDate': sd, 'data_source': 'hdf5'}
                entry['pubDate'] = max((r.get('pubDate', '') for r in by_date[sd].values()), default='')
                for key, rec in by_date[sd].items():
                    for k, v in rec.items():
                        if k in ('statDate', 'pubDate', 'hdf5_key', 'data_source'):
                            continue
                        entry[f'{key}_{k}'] = v
                merged.append(entry)

            return pd.DataFrame(merged)

        except Exception as e:
            warnings.warn(f"HDF5 fetch failed for {code_6d}: {e}")
            return pd.DataFrame()

    def _merge_one_row_per_year(self, df_ak: pd.DataFrame, df_h5: pd.DataFrame) -> pd.DataFrame:
        """akshare行优先，HDF5补充缺失年份"""
        if df_ak.empty and df_h5.empty:
            return pd.DataFrame()
        if df_ak.empty:
            return df_h5
        if df_h5.empty:
            return df_ak

        # [FIX G2-1] concat前：重置索引 + 去除重复列名
        df_ak = df_ak.loc[:, ~df_ak.columns.duplicated()] if not df_ak.empty else df_ak
        df_h5 = df_h5.loc[:, ~df_h5.columns.duplicated()] if not df_h5.empty else df_h5
        df_ak = df_ak.reset_index(drop=True) if not df_ak.empty else df_ak
        df_h5 = df_h5.reset_index(drop=True) if not df_h5.empty else df_h5

        # 优先使用akshare数据（更及时），HDF5仅用于填补akshare缺失的年份
        if df_ak.empty and df_h5.empty:
            return pd.DataFrame()
        if df_ak.empty:
            return df_h5
        if df_h5.empty:
            return df_ak
        # 去除HDF5中与akshare重复的列（保留akshare版本，akshare更及时）
        ak_cols = set(df_ak.columns)
        h5_deduped = df_h5[[c for c in df_h5.columns if c not in ak_cols]]
        # 用statDate作为key，只从HDF5补充akshare没有的年份
        ak_years = set(df_ak['statDate'].astype(str)) if 'statDate' in df_ak.columns else set()
        h5_extra = h5_deduped[~h5_deduped['statDate'].astype(str).isin(ak_years)] if 'statDate' in h5_deduped.columns else pd.DataFrame()
        all_rows = pd.concat([df_ak, h5_extra], sort=False)
        if 'statDate' in all_rows.columns:
            all_rows = all_rows.drop_duplicates(subset=['statDate'], keep='first')
        # 去除concat产生的重复列（如果有）
        all_rows = all_rows.loc[:, ~all_rows.columns.duplicated()]
        return all_rows

    def _compute_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算衍生指标

        [FIX G2-2] 净现比溯源：
        - akshare有原始数据，用 operating_cf / net_profit 计算
        - HDF5降级时：cashflow_cfo_to_net_profit_ratio 是预计算比率，
          无法从原始列验证（cashflow表只存比率不存绝对值），
          标记 confidence=low 说明数据不可独立验证
        """
        if df.empty:
            return df
        df = df.copy()
        # [FIX G2-3] 去除重复列名（akshare多表concat可能产生）
        df = df.loc[:, ~df.columns.duplicated()]

        net_p = self._get_col(df, ['net_profit', 'profit_net_profit'])
        rev = self._get_col(df, ['revenue', 'profit_revenue'])

        # 净现比计算策略
        op_cf = self._get_col(df, ['operating_cf', 'cashflow_operating_cf'])
        cfo_ratio_col = self._get_col(df, ['cashflow_cfo_to_net_profit_ratio'])

        if op_cf and net_p:
            # 有原始列：用经营CF / 净利润 计算（可溯源）
            df['cfo_to_net_profit'] = (df[op_cf] / df[net_p].replace(0, np.nan)).clip(-10, 10)
            df['cfo_confidence'] = 'high'
        elif cfo_ratio_col is not None:
            # [FIX G2-2] HDF5降级：使用预计算比率，但标记不可验证
            # cashflow表只存比率，原始CF/净利润不可得，confidence=low
            df['cfo_to_net_profit'] = df[cfo_ratio_col].clip(-10, 10)
            df['cfo_confidence'] = 'low'
        elif net_p:
            op_cf_f1 = self._get_col(df, ['cashflow_f1'])  # HDF5绝对值列
            if op_cf_f1:
                df['cfo_to_net_profit'] = (df[op_cf_f1] / df[net_p].replace(0, np.nan)).clip(-10, 10)
                df['cfo_confidence'] = 'medium'

        # 营收增速
        if rev:
            df['revenue_growth'] = df[rev].pct_change()

        # 净利润增速
        if net_p:
            df['profit_growth'] = df[net_p].pct_change()

        # ROIC
        eq = self._get_col(df, ['equity', 'balance_equity'])
        ta = self._get_col(df, ['total_assets', 'balance_total_assets'])
        if net_p and ta and eq:
            ic = df[eq] + (df[ta] - df[eq]).fillna(0)
            ic = ic.replace(0, np.nan)
            df['roic'] = (df[net_p] / ic).clip(-2, 2)

        # 标准别名
        if 'profit_roe' in df.columns:
            df['roe'] = df['profit_roe']
        elif 'dupont_roe' in df.columns:
            df['roe'] = df['dupont_roe']

        if rev:
            df['revenue'] = df[rev]
        if net_p:
            df['net_profit'] = df[net_p]

        return df

    def _get_col(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    def _annotate_gaap(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or 'statDate' not in df.columns:
            return df
        df = df.copy()
        df['gaap_breakpoint'] = df['statDate'].apply(
            lambda x: 'PRE_2007' if str(x) < '2007-01-01' else 'POST_2007'
        )
        return df

    def _normalize_code(self, code: str) -> str:
        digits = "".join(ch for ch in code if ch.isdigit)
        return digits[-6:] if len(digits) >= 6 else code
