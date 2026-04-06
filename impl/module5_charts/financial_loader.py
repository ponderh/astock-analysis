# -*- coding: utf-8 -*-
"""
财务数据加载器 - FinancialDataLoader
对接模块2的财务数据输出，严格按照 CONTRACT.md 附录A的 JSON Schema 实现字段校验
"""

import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path


# JSON Schema 定义（来自 CONTRACT.md 附录A）
FINANCIAL_DATA_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["stock_code", "years", "financial_metrics"],
    "properties": {
        "stock_code": {"type": "string", "description": "股票代码"},
        "years": {"type": "array", "items": {"type": "integer"}, "description": "数据年份列表"},
        "financial_metrics": {
            "type": "object",
            "required": [
                "revenue", "net_profit", "roe", "roic", "eps", "dps",
                "cfo", "total_assets", "net_assets", "gross_margin", "debt_ratio"
            ],
            "properties": {
                "revenue": {"type": "array", "items": {"type": "number"}, "description": "营业收入序列"},
                "net_profit": {"type": "array", "items": {"type": "number"}, "description": "净利润序列"},
                "roe": {"type": "array", "items": {"type": "number"}, "description": "ROE序列"},
                "roic": {"type": "array", "items": {"type": "number"}, "description": "ROIC序列"},
                "wacc": {"type": "array", "items": {"type": "number"}, "description": "WACC序列"},
                "eps": {"type": "array", "items": {"type": "number"}, "description": "EPS序列"},
                "dps": {"type": "array", "items": {"type": "number"}, "description": "DPS序列"},
                "cfo": {"type": "array", "items": {"type": "number"}, "description": "经营现金流序列"},
                "total_assets": {"type": "array", "items": {"type": "number"}, "description": "总资产序列"},
                "net_assets": {"type": "array", "items": {"type": "number"}, "description": "净资产序列"},
                "gross_margin": {"type": "array", "items": {"type": "number"}, "description": "毛利率序列"},
                "debt_ratio": {"type": "array", "items": {"type": "number"}, "description": "资产负债率序列"},
                "interest_bearing_debt_ratio": {"type": "array", "items": {"type": "number"}, "description": "有息负债率序列"},
                "pe": {"type": "array", "items": {"type": "number"}, "description": "PE序列"},
                "pb": {"type": "array", "items": {"type": "number"}, "description": "PB序列"},
                "ps": {"type": "array", "items": {"type": "number"}, "description": "PS序列"},
                "dupont_net_margin": {"type": "array", "items": {"type": "number"}, "description": "杜邦-净利率序列"},
                "dupont_asset_turnover": {"type": "array", "items": {"type": "number"}, "description": "杜邦-资产周转率序列"},
                "dupont_equity_multiplier": {"type": "array", "items": {"type": "number"}, "description": "杜邦-权益乘数序列"},
                "cumulative_dps": {"type": "array", "items": {"type": "number"}, "description": "累计分红序列"},
                "quarterly_revenue": {"type": "array", "items": {"type": "number"}, "description": "季度营收（4*N）"},
                "quarterly_profit": {"type": "array", "items": {"type": "number"}, "description": "季度净利润（4*N）"}
            }
        }
    }
}


class SchemaValidationError(Exception):
    """Schema验证错误异常"""
    pass


class FinancialDataLoader:
    """
    财务数据加载器
    
    负责：
    1. 加载模块2输出的JSON财务数据
    2. 按照 CONTRACT.md 附录A的 Schema 进行字段校验
    3. 提供标准化的数据访问接口
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化数据加载器
        
        Args:
            data_dir: 数据目录路径，默认为模块2的输出目录
        """
        self.data_dir = data_dir or self._get_default_data_dir()
        self._data: Dict[str, Any] = {}
        self._validated = False
    
    def _get_default_data_dir(self) -> str:
        """获取默认数据目录（模块2输出目录）"""
        # 假设模块2输出在 ../module2_financial/output/
        module_dir = Path(__file__).parent.parent
        return str(module_dir / "module2_financial" / "output")
    
    def load(self, file_path: str) -> Dict[str, Any]:
        """
        加载JSON文件并验证Schema
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            验证通过的数据字典
            
        Raises:
            FileNotFoundError: 文件不存在
            SchemaValidationError: Schema验证失败
            json.JSONDecodeError: JSON解析失败
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"数据文件不存在: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        self._validate_schema(raw_data)
        self._data = raw_data
        self._validated = True
        return self._data
    
    def load_from_dir(self, stock_code: str) -> Dict[str, Any]:
        """
        从数据目录加载指定股票的财务数据
        
        Args:
            stock_code: 股票代码（如 '000001'）
            
        Returns:
            验证通过的数据字典
        """
        file_path = os.path.join(self.data_dir, f"{stock_code}_financial.json")
        return self.load(file_path)
    
    def _validate_schema(self, data: Dict[str, Any]) -> None:
        """
        验证数据是否符合Schema定义
        
        Args:
            data: 待验证的数据
            
        Raises:
            SchemaValidationError: Schema验证失败
        """
        errors = []
        
        # 验证顶层必需字段
        required_fields = ['stock_code', 'years', 'financial_metrics']
        for field in required_fields:
            if field not in data:
                errors.append(f"缺少必需字段: {field}")
        
        if errors:
            raise SchemaValidationError(f"Schema验证失败:\n" + "\n".join(errors))
        
        # 验证 stock_code 类型
        if not isinstance(data['stock_code'], str):
            errors.append(f"stock_code 应为字符串类型，实际为: {type(data['stock_code']).__name__}")
        
        # 验证 years 数组
        if not isinstance(data['years'], list):
            errors.append(f"years 应为数组类型，实际为: {type(data['years']).__name__}")
        else:
            for i, year in enumerate(data['years']):
                if not isinstance(year, int):
                    errors.append(f"years[{i}] 应为整数类型，实际为: {type(year).__name__}")
        
        # 验证 financial_metrics 对象
        if not isinstance(data['financial_metrics'], dict):
            errors.append(f"financial_metrics 应为对象类型，实际为: {type(data['financial_metrics']).__name__}")
        else:
            metrics_errors = self._validate_financial_metrics(data['financial_metrics'], data['years'])
            errors.extend(metrics_errors)
        
        if errors:
            raise SchemaValidationError(f"Schema验证失败:\n" + "\n".join(errors))
    
    def _validate_financial_metrics(self, metrics: Dict[str, Any], years: List[int]) -> List[str]:
        """
        验证 financial_metrics 内部的字段
        
        Args:
            metrics: 财务指标字典
            years: 年份列表（用于验证数组长度）
            
        Returns:
            错误信息列表
        """
        errors = []
        expected_year_count = len(years)
        
        # 必需字段（来自Schema required）
        required_metrics = [
            'revenue', 'net_profit', 'roe', 'roic', 'eps', 'dps',
            'cfo', 'total_assets', 'net_assets', 'gross_margin', 'debt_ratio'
        ]
        
        for field in required_metrics:
            if field not in metrics:
                errors.append(f"缺少必需财务指标: {field}")
                continue
            
            field_errors = self._validate_number_array(
                metrics[field], field, expected_year_count
            )
            errors.extend(field_errors)
        
        # 可选字段（允许缺失，但如果有值则需验证）
        optional_metrics = [
            'wacc', 'interest_bearing_debt_ratio', 'pe', 'pb', 'ps',
            'dupont_net_margin', 'dupont_asset_turnover', 'dupont_equity_multiplier',
            'cumulative_dps', 'quarterly_revenue', 'quarterly_profit'
        ]
        
        for field in optional_metrics:
            if field in metrics and metrics[field] is not None:
                # 季度数据长度应该是 years * 4
                if field in ['quarterly_revenue', 'quarterly_profit']:
                    expected_count = expected_year_count * 4
                else:
                    expected_count = expected_year_count
                
                field_errors = self._validate_number_array(
                    metrics[field], field, expected_count
                )
                errors.extend(field_errors)
        
        return errors
    
    def _validate_number_array(self, value: Any, field_name: str, expected_length: int) -> List[str]:
        """
        验证数值数组
        
        Args:
            value: 待验证的值
            field_name: 字段名称（用于错误信息）
            expected_length: 期望的数组长度
            
        Returns:
            错误信息列表
        """
        errors = []
        
        if not isinstance(value, list):
            errors.append(f"{field_name} 应为数组类型，实际为: {type(value).__name__}")
            return errors
        
        if len(value) != expected_length:
            errors.append(
                f"{field_name} 数组长度不匹配: 期望 {expected_length} "
                f"(基于{expected_length // 4 if expected_length > len(value) else 0}年数据)，"
                f"实际为 {len(value)}"
            )
            return errors
        
        for i, item in enumerate(value):
            if not isinstance(item, (int, float)):
                errors.append(
                    f"{field_name}[{i}] 应为数值类型，实际为: {type(item).__name__}"
                )
        
        return errors
    
    def get_stock_code(self) -> str:
        """获取股票代码"""
        return self._data.get('stock_code', '')
    
    def get_years(self) -> List[int]:
        """获取年份列表"""
        return self._data.get('years', [])
    
    def get_financial_metrics(self) -> Dict[str, List[float]]:
        """获取所有财务指标"""
        return self._data.get('financial_metrics', {})
    
    def get_metric(self, metric_name: str) -> Optional[List[float]]:
        """
        获取指定财务指标
        
        Args:
            metric_name: 指标名称
            
        Returns:
            指标数值列表，若不存在返回 None
        """
        metrics = self._data.get('financial_metrics', {})
        return metrics.get(metric_name)
    
    def get_revenue(self) -> Optional[List[float]]:
        """获取营业收入序列"""
        return self.get_metric('revenue')
    
    def get_net_profit(self) -> Optional[List[float]]:
        """获取净利润序列"""
        return self.get_metric('net_profit')
    
    def get_roe(self) -> Optional[List[float]]:
        """获取ROE序列"""
        return self.get_metric('roe')
    
    def get_roic(self) -> Optional[List[float]]:
        """获取ROIC序列"""
        return self.get_metric('roic')
    
    def get_wacc(self) -> Optional[List[float]]:
        """获取WACC序列"""
        return self.get_metric('wacc')
    
    def get_eps(self) -> Optional[List[float]]:
        """获取EPS序列"""
        return self.get_metric('eps')
    
    def get_dps(self) -> Optional[List[float]]:
        """获取DPS序列"""
        return self.get_metric('dps')
    
    def get_cfo(self) -> Optional[List[float]]:
        """获取经营现金流序列"""
        return self.get_metric('cfo')
    
    def get_total_assets(self) -> Optional[List[float]]:
        """获取总资产序列"""
        return self.get_metric('total_assets')
    
    def get_net_assets(self) -> Optional[List[float]]:
        """获取净资产序列"""
        return self.get_metric('net_assets')
    
    def get_gross_margin(self) -> Optional[List[float]]:
        """获取毛利率序列"""
        return self.get_metric('gross_margin')
    
    def get_debt_ratio(self) -> Optional[List[float]]:
        """获取资产负债率序列"""
        return self.get_metric('debt_ratio')
    
    def get_interest_bearing_debt_ratio(self) -> Optional[List[float]]:
        """获取有息负债率序列"""
        return self.get_metric('interest_bearing_debt_ratio')
    
    def get_pe(self) -> Optional[List[float]]:
        """获取PE序列"""
        return self.get_metric('pe')
    
    def get_pb(self) -> Optional[List[float]]:
        """获取PB序列"""
        return self.get_metric('pb')
    
    def get_ps(self) -> Optional[List[float]]:
        """获取PS序列"""
        return self.get_metric('ps')
    
    def get_dupont_net_margin(self) -> Optional[List[float]]:
        """获取杜邦-净利率序列"""
        return self.get_metric('dupont_net_margin')
    
    def get_dupont_asset_turnover(self) -> Optional[List[float]]:
        """获取杜邦-资产周转率序列"""
        return self.get_metric('dupont_asset_turnover')
    
    def get_dupont_equity_multiplier(self) -> Optional[List[float]]:
        """获取杜邦-权益乘数序列"""
        return self.get_metric('dupont_equity_multiplier')
    
    def get_cumulative_dps(self) -> Optional[List[float]]:
        """获取累计分红序列"""
        return self.get_metric('cumulative_dps')
    
    def get_quarterly_revenue(self) -> Optional[List[float]]:
        """获取季度营收序列"""
        return self.get_metric('quarterly_revenue')
    
    def get_quarterly_profit(self) -> Optional[List[float]]:
        """获取季度净利润序列"""
        return self.get_metric('quarterly_profit')
    
    def is_validated(self) -> bool:
        """检查数据是否已通过Schema验证"""
        return self._validated
    
    def to_chart_data(self) -> Dict[str, Any]:
        """
        转换为图表可直接使用的格式
        
        Returns:
            包含 years, metrics, stock_code 的字典
        """
        return {
            'stock_code': self.get_stock_code(),
            'years': self.get_years(),
            'metrics': self.get_financial_metrics()
        }


# 便捷函数
def load_financial_data(file_path: str) -> FinancialDataLoader:
    """
    便捷函数：加载并验证财务数据
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        FinancialDataLoader 实例
    """
    loader = FinancialDataLoader()
    loader.load(file_path)
    return loader


if __name__ == '__main__':
    # 示例用法
    print("FinancialDataLoader 模块")
    print("使用方法:")
    print("  from financial_loader import FinancialDataLoader")
    print("  loader = FinancialDataLoader()")
    print("  data = loader.load_from_dir('000001')")
    print("  revenue = loader.get_revenue()")