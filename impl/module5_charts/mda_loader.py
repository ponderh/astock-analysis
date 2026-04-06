# -*- coding: utf-8 -*-
"""
MD&A数据加载器 - MD&ADataLoader
对接模块6的MD&A分析结果，严格按照 CONTRACT.md 附录A的 JSON Schema 实现字段校验
"""

import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path


# JSON Schema 定义（来自 CONTRACT.md 附录A）
MDA_DATA_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["stock_code", "strategic_commitments", "key_strategic_themes", "risk_factors"],
    "properties": {
        "stock_code": {"type": "string"},
        "strategic_commitments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "commitment": {"type": "string"},
                    "time_horizon": {"type": "string"},
                    "quantitative_target": {"type": "string"}
                }
            }
        },
        "key_strategic_themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "description": {"type": "string"}
                }
            }
        },
        "risk_factors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "risk": {"type": "string"},
                    "mitigation": {"type": "string"}
                }
            }
        }
    }
}


class SchemaValidationError(Exception):
    """Schema验证错误异常"""
    pass


class MDADataLoader:
    """
    MD&A数据加载器
    
    负责：
    1. 加载模块6输出的JSON MD&A分析数据
    2. 按照 CONTRACT.md 附录A的 Schema 进行字段校验
    3. 提供标准化的数据访问接口
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化数据加载器
        
        Args:
            data_dir: 数据目录路径，默认为模块6的输出目录
        """
        self.data_dir = data_dir or self._get_default_data_dir()
        self._data: Dict[str, Any] = {}
        self._validated = False
    
    def _get_default_data_dir(self) -> str:
        """获取默认数据目录（模块6输出目录）"""
        # 假设模块6输出在 ../module6_mda/output/
        module_dir = Path(__file__).parent.parent
        return str(module_dir / "module6_mda" / "output")
    
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
        从数据目录加载指定股票的MD&A数据
        
        Args:
            stock_code: 股票代码（如 '000001'）
            
        Returns:
            验证通过的数据字典
        """
        file_path = os.path.join(self.data_dir, f"{stock_code}_mda.json")
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
        required_fields = ['stock_code', 'strategic_commitments', 'key_strategic_themes', 'risk_factors']
        for field in required_fields:
            if field not in data:
                errors.append(f"缺少必需字段: {field}")
        
        if errors:
            raise SchemaValidationError(f"Schema验证失败:\n" + "\n".join(errors))
        
        # 验证 stock_code 类型
        if not isinstance(data['stock_code'], str):
            errors.append(f"stock_code 应为字符串类型，实际为: {type(data['stock_code']).__name__}")
        
        # 验证数组字段
        array_fields = {
            'strategic_commitments': self._validate_strategic_commitments,
            'key_strategic_themes': self._validate_key_strategic_themes,
            'risk_factors': self._validate_risk_factors
        }
        
        for field_name, validator in array_fields.items():
            if not isinstance(data[field_name], list):
                errors.append(f"{field_name} 应为数组类型，实际为: {type(data[field_name]).__name__}")
            else:
                field_errors = validator(data[field_name])
                errors.extend(field_errors)
        
        if errors:
            raise SchemaValidationError(f"Schema验证失败:\n" + "\n".join(errors))
    
    def _validate_strategic_commitments(self, items: List[Any]) -> List[str]:
        """
        验证战略承诺数组
        
        Args:
            items: strategic_commitments 数组
            
        Returns:
            错误信息列表
        """
        errors = []
        
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"strategic_commitments[{i}] 应为对象类型，实际为: {type(item).__name__}")
                continue
            
            # 验证必需字段
            required = ['commitment', 'time_horizon', 'quantitative_target']
            for field in required:
                if field not in item:
                    errors.append(f"strategic_commitments[{i}] 缺少必需字段: {field}")
                
                # 验证字段类型
                if field in item and not isinstance(item[field], str):
                    errors.append(
                        f"strategic_commitments[{i}].{field} 应为字符串类型，"
                        f"实际为: {type(item[field]).__name__}"
                    )
        
        return errors
    
    def _validate_key_strategic_themes(self, items: List[Any]) -> List[str]:
        """
        验证关键战略主题数组
        
        Args:
            items: key_strategic_themes 数组
            
        Returns:
            错误信息列表
        """
        errors = []
        
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"key_strategic_themes[{i}] 应为对象类型，实际为: {type(item).__name__}")
                continue
            
            # 验证必需字段
            required = ['theme', 'description']
            for field in required:
                if field not in item:
                    errors.append(f"key_strategic_themes[{i}] 缺少必需字段: {field}")
                
                # 验证字段类型
                if field in item and not isinstance(item[field], str):
                    errors.append(
                        f"key_strategic_themes[{i}].{field} 应为字符串类型，"
                        f"实际为: {type(item[field]).__name__}"
                    )
        
        return errors
    
    def _validate_risk_factors(self, items: List[Any]) -> List[str]:
        """
        验证风险因素数组
        
        Args:
            items: risk_factors 数组
            
        Returns:
            错误信息列表
        """
        errors = []
        
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"risk_factors[{i}] 应为对象类型，实际为: {type(item).__name__}")
                continue
            
            # 验证必需字段
            required = ['risk', 'mitigation']
            for field in required:
                if field not in item:
                    errors.append(f"risk_factors[{i}] 缺少必需字段: {field}")
                
                # 验证字段类型
                if field in item and not isinstance(item[field], str):
                    errors.append(
                        f"risk_factors[{i}].{field} 应为字符串类型，"
                        f"实际为: {type(item[field]).__name__}"
                    )
        
        return errors
    
    def get_stock_code(self) -> str:
        """获取股票代码"""
        return self._data.get('stock_code', '')
    
    def get_strategic_commitments(self) -> List[Dict[str, str]]:
        """获取战略承诺列表"""
        return self._data.get('strategic_commitments', [])
    
    def get_key_strategic_themes(self) -> List[Dict[str, str]]:
        """获取关键战略主题列表"""
        return self._data.get('key_strategic_themes', [])
    
    def get_risk_factors(self) -> List[Dict[str, str]]:
        """获取风险因素列表"""
        return self._data.get('risk_factors', [])
    
    def get_commitment_texts(self) -> List[str]:
        """
        获取所有战略承诺的文本（用于词云）
        
        Returns:
            承诺文本列表
        """
        return [item.get('commitment', '') for item in self.get_strategic_commitments()]
    
    def get_theme_texts(self) -> List[str]:
        """
        获取所有战略主题的文本（用于词云）
        
        Returns:
            主题文本列表
        """
        themes = []
        for item in self.get_key_strategic_themes():
            themes.append(item.get('theme', ''))
            themes.append(item.get('description', ''))
        return themes
    
    def get_risk_texts(self) -> List[str]:
        """
        获取所有风险因素的文本（用于词云）
        
        Returns:
            风险文本列表
        """
        risks = []
        for item in self.get_risk_factors():
            risks.append(item.get('risk', ''))
            risks.append(item.get('mitigation', ''))
        return risks
    
    def get_all_texts(self) -> List[str]:
        """
        获取所有MD&A文本（用于词云）
        
        Returns:
            所有文本的合并列表
        """
        texts = []
        texts.extend(self.get_commitment_texts())
        texts.extend(self.get_theme_texts())
        texts.extend(self.get_risk_texts())
        return [t for t in texts if t]  # 过滤空字符串
    
    def get_commitment_summary(self) -> Dict[str, Any]:
        """
        获取战略承诺摘要
        
        Returns:
            包含承诺数量和时间范围的字典
        """
        commitments = self.get_strategic_commitments()
        time_horizons = set()
        
        for item in commitments:
            if item.get('time_horizon'):
                time_horizons.add(item['time_horizon'])
        
        return {
            'count': len(commitments),
            'time_horizons': list(time_horizons)
        }
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """
        获取风险因素摘要
        
        Returns:
            包含风险数量的字典
        """
        return {
            'count': len(self.get_risk_factors())
        }
    
    def is_validated(self) -> bool:
        """检查数据是否已通过Schema验证"""
        return self._validated
    
    def to_chart_data(self) -> Dict[str, Any]:
        """
        转换为图表可直接使用的格式
        
        Returns:
            包含 stock_code, commitments, themes, risks 的字典
        """
        return {
            'stock_code': self.get_stock_code(),
            'strategic_commitments': self.get_strategic_commitments(),
            'key_strategic_themes': self.get_key_strategic_themes(),
            'risk_factors': self.get_risk_factors(),
            'all_texts': self.get_all_texts()
        }


# 便捷函数
def load_mda_data(file_path: str) -> MDADataLoader:
    """
    便捷函数：加载并验证MD&A数据
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        MD&ADataLoader 实例
    """
    loader = MD&ADataLoader()
    loader.load(file_path)
    return loader


if __name__ == '__main__':
    # 示例用法
    print("MD&ADataLoader 模块")
    print("使用方法:")
    print("  from mda_loader import MD&ADataLoader")
    print("  loader = MD&ADataLoader()")
    print("  data = loader.load_from_dir('000001')")
    print("  commitments = loader.get_strategic_commitments()")
    print("  themes = loader.get_key_strategic_themes()")
    print("  risks = loader.get_risk_factors()")
    print("  all_texts = loader.get_all_texts()  # 用于词云")