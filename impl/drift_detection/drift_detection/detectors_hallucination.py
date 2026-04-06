"""
LLM幻觉漂移检测器

Phase 4 实现：
1. 监控结构化输出缺失率（strategic_commitments为空的比例）
2. 监控幻觉标记出现频率
3. 结合MiniMax和DeepSeek双模型一致性检测

依赖:
- module6_mda.analyzer.MultiProviderLLMAnalyzer
- drift_detection.models.DriftRecord
- drift_detection.config.DetectionConfig
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import DetectionConfig, get_config
from ..database import get_database
from ..models import (
    AlertLevel,
    AlertRecord,
    DriftDimension,
    DriftRecord,
    MetricType,
)


# ============================================================================
# 检测结果
# ============================================================================

@dataclass
class HallucinationDetectionResult:
    """幻觉检测结果"""
    is_drift: bool
    failure_rate: float  # 幻觉率
    threshold: float
    severity: AlertLevel
    
    # 详细指标
    missing_structure_rate: float = 0.0  # 结构化输出缺失率
    hallucination_markers_rate: float = 0.0  # 幻觉标记出现频率
    model_disagreement_rate: float = 0.0  # 双模型不一致率
    
    # 详细数据
    total_count: int = 0
    missing_structure_count: int = 0
    hallucination_marker_count: int = 0
    model_disagreement_count: int = 0
    
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# LLM幻觉检测器
# ============================================================================

class HallucinationDriftDetector:
    """
    LLM幻觉漂移检测器
    
    监控维度:
    1. 结构化输出缺失率 - strategic_commitments为空的比例
    2. 幻觉标记频率 - hallucination_flags出现频率
    3. 双模型一致性 - MiniMax vs DeepSeek 结果一致性
    """
    
    dimension = DriftDimension.LLM_HALLUCINATION
    
    def __init__(self, config: Optional[DetectionConfig] = None):
        """
        初始化检测器
        
        Args:
            config: 检测配置
        """
        if config is None:
            app_config = get_config()
            config = app_config.detection
        
        self.config = config
        self.db = get_database(config.db_path)
        
        # 双模型验证配置
        self._minimax_provider = None
        self._deepseek_provider = None
        self._setup_providers()
    
    def _setup_providers(self) -> None:
        """设置LLM Provider用于双模型验证"""
        # MiniMax配置
        minimax_key = os.environ.get('MINIMAX_API_KEY')
        if minimax_key:
            self._minimax_provider = {
                'id': 'minimax_primary',
                'name': 'MiniMax M2.7',
                'model': 'MiniMax-M2.7-highspeed',
                'api_key': minimax_key,
                'base_url': 'https://api.minimaxi.com/anthropic/v1',
                'api_style': 'anthropic',
            }
        
        # DeepSeek配置
        deepseek_key = os.environ.get('DEEPSEEK_API_KEY')
        if deepseek_key:
            self._deepseek_provider = {
                'id': 'deepseek',
                'name': 'DeepSeek',
                'model': 'deepseek-chat',
                'api_key': deepseek_key,
                'base_url': 'https://api.deepseek.com/v1',
                'api_style': 'openai',
            }
    
    def _get_metric_type(self) -> MetricType:
        return MetricType.HALLUCINATION_SCORE
    
    # =========================================================================
    # 记录接口
    # =========================================================================
    
    def record(
        self,
        stock_code: str,
        value: float,
        metadata: Dict[str, Any] = None,
    ) -> DriftRecord:
        """
        记录单次检测结果
        
        Args:
            stock_code: 股票代码
            value: 检测值（置信度/一致性评分）
            metadata: 附加元数据
            
        Returns:
            漂移记录
        """
        record = DriftRecord(
            stock_code=stock_code,
            dimension=self.dimension,
            metric=self._get_metric_type(),
            value=value,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )
        record.id = self.db.create_drift_record(record)
        return record
    
    def record_llm_analysis(
        self,
        stock_code: str,
        structured_data: Dict[str, Any],
        hallucination_flags: List[str],
        model_used: str = "",
    ) -> DriftRecord:
        """
        记录LLM分析结果
        
        Args:
            stock_code: 股票代码
            structured_data: 结构化分析结果
            hallucination_flags: 幻觉标记列表
            model_used: 使用的模型
            
        Returns:
            漂移记录
        """
        metadata = {
            'model_used': model_used,
            'hallucination_flags': hallucination_flags,
            'hallucination_marker_count': len(hallucination_flags),
        }
        
        # 检查结构化输出缺失
        is_missing_structure = self._check_missing_structure(structured_data)
        metadata['is_missing_structure'] = is_missing_structure
        
        # 计算置信度评分（基于幻觉标记）
        # 无幻觉标记 = 1.0，有标记则降低
        if hallucination_flags:
            confidence_score = max(0.0, 1.0 - len(hallucination_flags) * 0.1)
        else:
            confidence_score = 1.0
        
        return self.record(
            stock_code=stock_code,
            value=confidence_score,
            metadata=metadata,
        )
    
    def record_model_comparison(
        self,
        stock_code: str,
        minimax_data: Dict[str, Any],
        deepseek_data: Dict[str, Any],
        consistency: Dict[str, Any],
    ) -> DriftRecord:
        """
        记录双模型对比结果
        
        Args:
            stock_code: 股票代码
            minimax_data: MiniMax分析结果
            deepseek_data: DeepSeek分析结果
            consistency: 一致性检查结果
            
        Returns:
            漂移记录
        """
        metadata = {
            'minimax_data': self._extract_summary(minimax_data),
            'deepseek_data': self._extract_summary(deepseek_data),
            'consistency': consistency,
            'model_disagreement': consistency.get('status') == 'disagreement',
        }
        
        # 一致性评分：1.0 = 完全一致，0.0 = 完全不一致
        disagreement_count = len(consistency.get('disagreements', []))
        consistency_score = max(0.0, 1.0 - disagreement_count * 0.25)
        
        return self.record(
            stock_code=stock_code,
            value=consistency_score,
            metadata=metadata,
        )
    
    # =========================================================================
    # 检测逻辑
    # =========================================================================
    
    def _check_missing_structure(self, structured_data: Dict[str, Any]) -> bool:
        """检查结构化输出是否缺失（strategic_commitments为空）"""
        commitments = structured_data.get('strategic_commitments', [])
        
        # 视为缺失的情况：
        # 1. 字段不存在
        # 2. 为空列表
        # 3. 为空字符串
        if not commitments:
            return True
        
        if isinstance(commitments, str):
            return not commitments.strip()
        
        if isinstance(commitments, list):
            # 检查是否所有项都是空/无效
            return len(commitments) == 0
        
        return False
    
    def _extract_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """提取数据摘要用于存储"""
        return {
            'strategic_commitments_count': len(data.get('strategic_commitments', [])),
            'key_strategic_themes_count': len(data.get('key_strategic_themes', [])),
            'risk_factors_count': len(data.get('risk_factors', [])),
        }
    
    def detect(self) -> List[HallucinationDetectionResult]:
        """
        执行漂移检测
        
        计算当日各项幻觉率指标，与阈值比较
        """
        stats = self.get_daily_stats()
        
        if stats['total_count'] == 0:
            return []
        
        # 获取当日所有记录
        records = self.db.get_drift_records(
            dimension=self.dimension,
            limit=stats['total_count'],
        )
        
        total_count = len(records)
        
        # 1. 计算结构化输出缺失率
        missing_structure_count = sum(
            1 for r in records
            if r.metadata.get('is_missing_structure', False)
        )
        missing_structure_rate = missing_structure_count / total_count if total_count > 0 else 0
        
        # 2. 计算幻觉标记出现频率
        hallucination_marker_count = sum(
            1 for r in records
            if r.metadata.get('hallucination_marker_count', 0) > 0
        )
        hallucination_marker_rate = hallucination_marker_count / total_count if total_count > 0 else 0
        
        # 3. 计算双模型不一致率
        model_disagreement_count = sum(
            1 for r in records
            if r.metadata.get('model_disagreement', False)
        )
        model_disagreement_rate = model_disagreement_count / total_count if total_count > 0 else 0
        
        # 综合幻觉率 = max(缺失率, 标记率, 不一致率)
        hallucination_rate = max(
            missing_structure_rate,
            hallucination_marker_rate,
            model_disagreement_rate,
        )
        
        # 检查阈值
        if hallucination_rate >= self.config.hallucination_threshold:
            severity = self._calculate_severity(hallucination_rate)
            message = self._generate_message(
                hallucination_rate,
                missing_structure_rate,
                hallucination_marker_rate,
                model_disagreement_rate,
            )
            
            result = HallucinationDetectionResult(
                is_drift=True,
                failure_rate=hallucination_rate,
                threshold=self.config.hallucination_threshold,
                severity=severity,
                missing_structure_rate=missing_structure_rate,
                hallucination_markers_rate=hallucination_marker_rate,
                model_disagreement_rate=model_disagreement_rate,
                total_count=total_count,
                missing_structure_count=missing_structure_count,
                hallucination_marker_count=hallucination_marker_count,
                model_disagreement_count=model_disagreement_count,
                message=message,
                metadata={
                    'detection_time': datetime.now().isoformat(),
                    'dimension': self.dimension.value,
                },
            )
            return [result]
        
        return []
    
    def get_daily_stats(self, date: Optional[datetime] = None) -> dict:
        """
        获取每日统计
        
        Args:
            date: 日期，默认今天
            
        Returns:
            每日统计数据
        """
        date = date or datetime.now()
        return self.db.get_daily_stats(self.dimension, date)
    
    def _get_threshold(self) -> float:
        """获取幻觉率阈值"""
        return self.config.hallucination_threshold
    
    def _calculate_severity(self, current: float) -> AlertLevel:
        """计算告警级别"""
        if current >= self.config.critical_threshold:
            return AlertLevel.CRITICAL
        elif current >= self.config.warning_threshold:
            return AlertLevel.WARNING
        else:
            return AlertLevel.INFO
    
    def _generate_message(
        self,
        hallucination_rate: float,
        missing_structure_rate: float,
        hallucination_marker_rate: float,
        model_disagreement_rate: float,
    ) -> str:
        """生成告警消息"""
        return (
            f"LLM幻觉率告警: 当前幻觉率 {hallucination_rate:.2%}, "
            f"阈值 {self.config.hallucination_threshold:.2%}\n"
            f"  - 结构化输出缺失率: {missing_structure_rate:.2%}\n"
            f"  - 幻觉标记出现率: {hallucination_marker_rate:.2%}\n"
            f"  - 双模型不一致率: {model_disagreement_rate:.2%}\n"
            f"维度: {self.dimension.value}"
        )
    
    def create_alert(self, result: HallucinationDetectionResult) -> AlertRecord:
        """
        创建告警记录
        
        Args:
            result: 检测结果
            
        Returns:
            告警记录
        """
        alert = AlertRecord(
            dimension=result.severity,
            failure_rate=result.failure_rate,
            threshold=result.threshold,
            severity=result.severity,
            message=result.message,
            created_at=datetime.now(),
            metadata=result.metadata,
        )
        alert.id = self.db.create_alert_record(alert)
        return alert
    
    # =========================================================================
    # 双模型一致性检测（可独立调用）
    # =========================================================================
    
    def check_model_consistency(
        self,
        text: str,
        prompt_template: str,
    ) -> Dict[str, Any]:
        """
        检查MiniMax和DeepSeek模型一致性
        
        Args:
            text: 待分析文本
            prompt_template: 提示词模板
            
        Returns:
            一致性检查结果
        """
        if not self._minimax_provider or not self._deepseek_provider:
            return {
                'status': 'provider_not_available',
                'error': 'MiniMax or DeepSeek provider not configured',
            }
        
        # 调用双模型
        minimax_result = self._call_provider(
            text, prompt_template, self._minimax_provider, 8192
        )
        deepseek_result = self._call_provider(
            text, prompt_template, self._deepseek_provider, 8192
        )
        
        if not minimax_result or not deepseek_result:
            return {
                'status': 'api_failed',
                'error': 'Failed to call one or both providers',
            }
        
        # 解析结果
        minimax_parsed = self._parse_json_response(minimax_result)
        deepseek_parsed = self._parse_json_response(deepseek_result)
        
        # 一致性检查
        consistency = self._compare_results(minimax_parsed, deepseek_parsed)
        
        return {
            'status': 'completed',
            'minimax': minimax_parsed,
            'deepseek': deepseek_parsed,
            'consistency': consistency,
        }
    
    def _call_provider(
        self,
        text: str,
        prompt_template: str,
        provider: Dict,
        max_tokens: int,
    ) -> Optional[str]:
        """调用LLM Provider"""
        import requests
        
        prompt = prompt_template.replace('{text}', text[:8000])
        api_style = provider.get('api_style', 'openai')
        
        try:
            if api_style == 'anthropic':
                resp = requests.post(
                    f"{provider['base_url']}/messages",
                    headers={
                        'x-api-key': provider['api_key'],
                        'Content-Type': 'application/json',
                        'anthropic-version': '2023-06-01',
                        'anthropic-dangerous-direct-browser-access': 'true'
                    },
                    json={
                        'model': provider['model'],
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': max_tokens,
                        'temperature': 0.1,
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for block in data.get('content', []):
                        if block.get('type') == 'text':
                            return block['text']
            else:
                resp = requests.post(
                    f"{provider['base_url']}/chat/completions",
                    headers={
                        'Authorization': f"Bearer {provider['api_key']}",
                        'Content-Type': 'application/json',
                    },
                    json={
                        'model': provider['model'],
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': max_tokens,
                        'temperature': 0.1,
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    return resp.json()['choices'][0]['message']['content']
        except Exception:
            pass
        
        return None
    
    def _parse_json_response(self, raw_response: str) -> Dict[str, Any]:
        """解析JSON响应"""
        if not raw_response:
            return {}
        
        # 尝试从markdown代码块提取
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试直接解析
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            pass
        
        return {'raw_text': raw_response}
    
    def _compare_results(
        self,
        minimax_data: Dict[str, Any],
        deepseek_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """比较双模型结果"""
        disagreements = []
        
        # 对比战略性承诺数量
        m_commits = len(minimax_data.get('strategic_commitments', []))
        d_commits = len(deepseek_data.get('strategic_commitments', []))
        if abs(m_commits - d_commits) > 3:
            disagreements.append(f"strategic_commitments count diff: minimax={m_commits}, deepseek={d_commits}")
        
        # 对比主题数量
        m_themes = len(minimax_data.get('key_strategic_themes', []))
        d_themes = len(deepseek_data.get('key_strategic_themes', []))
        if abs(m_themes - d_themes) > 3:
            disagreements.append(f"key_strategic_themes count diff: minimax={m_themes}, deepseek={d_themes}")
        
        # 对比风险因素数量
        m_risks = len(minimax_data.get('risk_factors', []))
        d_risks = len(deepseek_data.get('risk_factors', []))
        if abs(m_risks - d_risks) > 3:
            disagreements.append(f"risk_factors count diff: minimax={m_risks}, deepseek={d_risks}")
        
        return {
            'status': 'disagreement' if disagreements else 'consistent',
            'disagreements': disagreements,
            'counts': {
                'minimax': {'commitments': m_commits, 'themes': m_themes, 'risks': m_risks},
                'deepseek': {'commitments': d_commits, 'themes': d_themes, 'risks': d_risks},
            },
        }


# ============================================================================
# 便捷函数
# ============================================================================

def get_detector(config: Optional[DetectionConfig] = None) -> HallucinationDriftDetector:
    """获取检测器实例"""
    return HallucinationDriftDetector(config)