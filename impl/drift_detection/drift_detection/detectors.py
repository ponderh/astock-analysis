"""
漂移检测器框架

包含Detector基类和三个具体检测器实现
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional

from .config import AppConfig, DetectionConfig, get_config
from .database import get_database
from .models import (
    AlertLevel,
    AlertRecord,
    DriftDimension,
    DriftRecord,
    MetricType,
)


@dataclass
class DetectionResult:
    """检测结果"""
    is_drift: bool
    dimension: DriftDimension
    failure_rate: float
    threshold: float
    severity: AlertLevel
    message: str
    metadata: dict = field(default_factory=dict)


class Detector(ABC):
    """
    检测器基类
    
    所有具体检测器需继承此类并实现detect方法
    """
    
    dimension: DriftDimension
    
    def __init__(self, config: Optional[DetectionConfig] = None):
        """
        初始化检测器
        
        Args:
            config: 检测配置
        """
        # 如果传入的是AppConfig，取其detection部分
        if config is None:
            app_config = get_config()
            config = app_config.detection
        elif isinstance(config, AppConfig):
            config = config.detection
        
        self.config = config
        self.db = get_database(self.config.db_path)
    
    def record(self, stock_code: str, value: float, metadata: dict = None) -> DriftRecord:
        """
        记录单次检测结果
        
        Args:
            stock_code: 股票代码
            value: 检测值
            metadata: 附加元数据
            
        Returns:
            创建的漂移记录
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
    
    @abstractmethod
    def _get_metric_type(self) -> MetricType:
        """获取指标类型"""
        pass
    
    @abstractmethod
    def detect(self) -> List[DetectionResult]:
        """
        执行漂移检测
        
        Returns:
            检测结果列表
        """
        pass
    
    def check_threshold(self, current_value: float) -> Optional[DetectionResult]:
        """
        检查是否触发阈值
        
        Args:
            current_value: 当前值
            
        Returns:
            检测结果，无漂移返回None
        """
        threshold = self._get_threshold()
        
        if current_value >= threshold:
            severity = self._calculate_severity(current_value, threshold)
            message = self._generate_message(current_value, threshold)
            
            return DetectionResult(
                is_drift=True,
                dimension=self.dimension,
                failure_rate=current_value,
                threshold=threshold,
                severity=severity,
                message=message,
                metadata={"current_value": current_value, "threshold": threshold},
            )
        
        return None
    
    @abstractmethod
    def _get_threshold(self) -> float:
        """获取阈值"""
        pass
    
    @abstractmethod
    def _calculate_severity(self, current: float, threshold: float) -> AlertLevel:
        """计算告警级别"""
        pass
    
    @abstractmethod
    def _generate_message(self, current: float, threshold: float) -> str:
        """生成告警消息"""
        pass
    
    def create_alert(self, result: DetectionResult) -> AlertRecord:
        """
        创建告警记录
        
        Args:
            result: 检测结果
            
        Returns:
            告警记录
        """
        alert = AlertRecord(
            dimension=result.dimension,
            failure_rate=result.failure_rate,
            threshold=result.threshold,
            severity=result.severity,
            message=result.message,
            created_at=datetime.now(),
            metadata=result.metadata,
        )
        alert.id = self.db.create_alert_record(alert)
        return alert
    
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


class LocateDriftDetector(Detector):
    """
    章节定位漂移检测器
    
    监控MD&A章节定位精度，置信度<0.6视为失败
    """
    
    dimension = DriftDimension.CHAPTER_LOCATOR
    
    def _get_metric_type(self) -> MetricType:
        return MetricType.CONFIDENCE
    
    def _get_threshold(self) -> float:
        """获取失败率阈值"""
        return self.config.locate_failure_threshold
    
    def _calculate_severity(self, current: float, threshold: float) -> AlertLevel:
        """计算告警级别"""
        if current >= self.config.critical_threshold:
            return AlertLevel.CRITICAL
        elif current >= self.config.warning_threshold:
            return AlertLevel.WARNING
        else:
            return AlertLevel.INFO
    
    def _generate_message(self, current: float, threshold: float) -> str:
        """生成告警消息"""
        return (
            f"章节定位失败率告警: 当前失败率 {current:.2%}, "
            f"阈值 {threshold:.2%}, 维度: {self.dimension.value}"
        )
    
    def record_confidence(
        self,
        stock_code: str,
        confidence: float,
        chapter: Optional[str] = None,
    ) -> DriftRecord:
        """
        记录章节定位置信度
        
        Args:
            stock_code: 股票代码
            confidence: 置信度
            chapter: 章节名称
            
        Returns:
            漂移记录
        """
        metadata = {}
        if chapter:
            metadata["chapter"] = chapter
        
        # 置信度<0.6视为失败
        is_failure = confidence < self.config.confidence_threshold
        
        return self.record(
            stock_code=stock_code,
            value=confidence if not is_failure else 0.0,
            metadata=metadata,
        )
    
    def detect(self) -> List[DetectionResult]:
        """
        执行漂移检测
        
        计算当日定位失败率，与阈值比较
        """
        stats = self.get_daily_stats()
        
        if stats["total_count"] == 0:
            return []
        
        # 计算失败率（置信度<0.6的比例）
        records = self.db.get_drift_records(
            dimension=self.dimension,
            limit=stats["total_count"],
        )
        
        failure_count = sum(
            1 for r in records
            if r.value < self.config.confidence_threshold
        )
        
        failure_rate = failure_count / stats["total_count"]
        
        result = self.check_threshold(failure_rate)
        
        if result:
            return [result]
        
        return []


class RuleDriftDetector(Detector):
    """
    规则引擎漂移检测器
    
    监控红旗引擎超时/异常/评分一致性
    """
    
    dimension = DriftDimension.REDFLAG_ENGINE
    
    def _get_metric_type(self) -> MetricType:
        return MetricType.ERROR_RATE
    
    def _get_threshold(self) -> float:
        """获取错误率阈值"""
        return self.config.rule_error_threshold
    
    def _calculate_severity(self, current: float, threshold: float) -> AlertLevel:
        """计算告警级别"""
        if current >= self.config.critical_threshold:
            return AlertLevel.CRITICAL
        elif current >= self.config.warning_threshold:
            return AlertLevel.WARNING
        else:
            return AlertLevel.INFO
    
    def _generate_message(self, current: float, threshold: float) -> str:
        """生成告警消息"""
        return (
            f"规则引擎错误率告警: 当前错误率 {current:.2%}, "
            f"阈值 {threshold:.2%}, 维度: {self.dimension.value}"
        )
    
    def record_execution(
        self,
        stock_code: str,
        is_timeout: bool = False,
        is_error: bool = False,
        score: Optional[float] = None,
        verdict: Optional[str] = None,
        execution_time: Optional[float] = None,
    ) -> DriftRecord:
        """
        记录规则引擎执行结果
        
        Args:
            stock_code: 股票代码
            is_timeout: 是否超时
            is_error: 是否异常
            score: 评分
            verdict: 红旗判定
            execution_time: 执行时间(秒)
            
        Returns:
            漂移记录
        """
        metadata = {
            "is_timeout": is_timeout,
            "is_error": is_error,
        }
        
        if score is not None:
            metadata["score"] = score
        if verdict is not None:
            metadata["verdict"] = verdict
        if execution_time is not None:
            metadata["execution_time"] = execution_time
        
        # 判断是否为异常
        is_anomaly = False
        
        # 检查超时
        if is_timeout or (execution_time and execution_time > self.config.timeout_threshold):
            is_anomaly = True
        
        # 检查score异常
        if score is not None:
            if score < 0 or score > 100:
                is_anomaly = True
        
        # 检查score/verdict不一致
        if score is not None and verdict is not None:
            expected_red = score >= self.config.red_flag_score_threshold
            actual_red = verdict.lower() in ["red", "存在", "有"]
            if expected_red != actual_red:
                is_anomaly = True
                metadata["inconsistency"] = True
        
        # 返回值: 1表示异常, 0表示正常
        return self.record(
            stock_code=stock_code,
            value=1.0 if is_anomaly else 0.0,
            metadata=metadata,
        )
    
    def detect(self) -> List[DetectionResult]:
        """
        执行漂移检测
        
        计算当日错误率，与阈值比较
        """
        stats = self.get_daily_stats()
        
        if stats["total_count"] == 0:
            return []
        
        # 错误率 = 异常次数 / 总次数
        error_rate = stats["avg_value"]
        
        result = self.check_threshold(error_rate)
        
        if result:
            return [result]
        
        return []


class HallucinationDriftDetector(Detector):
    """
    LLM幻觉漂移检测器
    
    监控LLM分析结果可信度，检测逻辑矛盾和一致性
    """
    
    dimension = DriftDimension.LLM_HALLUCINATION
    
    def _get_metric_type(self) -> MetricType:
        return MetricType.HALLUCINATION_SCORE
    
    def _get_threshold(self) -> float:
        """获取幻觉率阈值"""
        return self.config.hallucination_threshold
    
    def _calculate_severity(self, current: float, threshold: float) -> AlertLevel:
        """计算告警级别"""
        if current >= self.config.critical_threshold:
            return AlertLevel.CRITICAL
        elif current >= self.config.warning_threshold:
            return AlertLevel.WARNING
        else:
            return AlertLevel.INFO
    
    def _generate_message(self, current: float, threshold: float) -> str:
        """生成告警消息"""
        return (
            f"LLM幻觉率告警: 当前幻觉率 {current:.2%}, "
            f"阈值 {threshold:.2%}, 维度: {self.dimension.value}"
        )
    
    def record_confidence(
        self,
        stock_code: str,
        confidence_score: float,
        contradictions: Optional[List[str]] = None,
        validation_details: Optional[dict] = None,
    ) -> DriftRecord:
        """
        记录LLM分析置信度
        
        Args:
            stock_code: 股票代码
            confidence_score: 置信度评分(0-1)
            contradictions: 检测到的逻辑矛盾列表
            validation_details: 验证详情
            
        Returns:
            漂移记录
        """
        metadata = {}
        
        if contradictions:
            metadata["contradictions"] = contradictions
            metadata["contradiction_count"] = len(contradictions)
        
        if validation_details:
            metadata["validation_details"] = validation_details
        
        # 置信度低于阈值视为存在幻觉
        is_hallucination = confidence_score < self.config.confidence_threshold
        
        return self.record(
            stock_code=stock_code,
            value=confidence_score,
            metadata=metadata,
        )
    
    def detect_contradiction(
        self,
        analysis_result: dict,
    ) -> tuple[bool, List[str]]:
        """
        检测逻辑矛盾
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            (是否存在矛盾, 矛盾列表)
        """
        contradictions = []
        
        # 检查关键字段是否存在矛盾
        # 例如: 利润大幅增长但现金流为负
        
        # TODO: 实现具体矛盾检测逻辑
        # 占位实现，返回无矛盾
        
        return len(contradictions) > 0, contradictions
    
    def cross_validate(
        self,
        llm_result: str,
        facts: List[dict],
    ) -> float:
        """
        交叉验证一致性
        
        Args:
            llm_result: LLM分析结果
            facts: 事实列表
            
        Returns:
            一致性评分(0-1)
        """
        # TODO: 实现具体交叉验证逻辑
        # 占位实现，返回1.0
        
        return 1.0
    
    def detect(self) -> List[DetectionResult]:
        """
        执行漂移检测
        
        计算当日幻觉率，与阈值比较
        """
        stats = self.get_daily_stats()
        
        if stats["total_count"] == 0:
            return []
        
        # 幻觉率 = 置信度低于阈值的比例
        records = self.db.get_drift_records(
            dimension=self.dimension,
            limit=stats["total_count"],
        )
        
        hallucination_count = sum(
            1 for r in records
            if r.value < self.config.confidence_threshold
        )
        
        hallucination_rate = hallucination_count / stats["total_count"]
        
        result = self.check_threshold(hallucination_rate)
        
        if result:
            return [result]
        
        return []


# 检测器工厂
def get_detector(dimension: DriftDimension) -> Detector:
    """
    获取检测器实例
    
    Args:
        dimension: 漂移维度
        
    Returns:
        检测器实例
    """
    detectors = {
        DriftDimension.CHAPTER_LOCATOR: LocateDriftDetector,
        DriftDimension.REDFLAG_ENGINE: RuleDriftDetector,
        DriftDimension.LLM_HALLUCINATION: HallucinationDriftDetector,
    }
    
    detector_class = detectors.get(dimension)
    if not detector_class:
        raise ValueError(f"Unknown dimension: {dimension}")
    
    return detector_class()


def get_all_detectors() -> List[Detector]:
    """获取所有检测器"""
    return [
        LocateDriftDetector(),
        RuleDriftDetector(),
        HallucinationDriftDetector(),
    ]
