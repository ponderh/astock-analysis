"""
漂移监控核心模块

整合LocateDriftDetector、RuleDriftDetector、HallucinationDriftDetector
提供统一的监控接口
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .alerts import AlertEvent, AlertManager, get_alert_manager
from .config import AppConfig, get_config
from .database import get_database
from .detectors import (
    DetectionResult,
    Detector,
    HallucinationDriftDetector,
    LocateDriftDetector,
    RuleDriftDetector,
    get_all_detectors,
    get_detector,
)
from .models import AlertLevel, AlertRecord, DriftDimension, DriftRecord

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class MonitorStatus:
    """监控状态"""
    dimension: DriftDimension
    last_check_time: Optional[datetime]
    last_failure_rate: float
    is_drift_detected: bool
    alert_count_today: int
    metadata: dict = field(default_factory=dict)


@dataclass
class DriftStatus:
    """漂移状态汇总"""
    timestamp: datetime
    overall_healthy: bool
    dimensions: Dict[str, MonitorStatus]
    recent_alerts: List[AlertRecord]
    summary: str


class DriftMonitor:
    """
    漂移监控器
    
    整合三个检测器，提供统一的监控接口
    支持定时检测和手动触发
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        初始化漂移监控器
        
        Args:
            config: 应用配置
        """
        self.config = config or get_config()
        self.db = get_database(self.config.detection.db_path)
        
        # 初始化检测器
        self.locate_detector = LocateDriftDetector(self.config)
        self.rule_detector = RuleDriftDetector(self.config)
        self.hallucination_detector = HallucinationDriftDetector(self.config)
        
        # 初始化告警管理器
        self.alert_manager = get_alert_manager(self.config)
        
        # 注册告警回调
        self.alert_manager.register_callback(self._on_alert)
        
        # 监控状态
        self._status: Dict[DriftDimension, MonitorStatus] = {}
        
        # 告警回调列表
        self._alert_callbacks: List[callable] = []
        
        logger.info("DriftMonitor initialized")
    
    def _on_alert(self, event: AlertEvent) -> None:
        """告警回调处理"""
        for callback in self._alert_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    def register_alert_callback(self, callback: callable) -> None:
        """
        注册告警回调
        
        Args:
            callback: 回调函数，接收AlertEvent参数
        """
        self._alert_callbacks.append(callback)
    
    # ==================== 章节定位监控 ====================
    
    def record_locate_confidence(
        self,
        stock_code: str,
        confidence: float,
        chapter: Optional[str] = None,
    ) -> DriftRecord:
        """
        记录章节定位结果
        
        Args:
            stock_code: 股票代码
            confidence: 置信度
            chapter: 章节名称
            
        Returns:
            漂移记录
        """
        return self.locate_detector.record_confidence(
            stock_code=stock_code,
            confidence=confidence,
            chapter=chapter,
        )
    
    def get_locate_daily_stats(self, date: Optional[datetime] = None) -> dict:
        """
        获取章节定位每日统计
        
        Args:
            date: 日期，默认今天
            
        Returns:
            每日统计数据
        """
        return self.locate_detector.get_daily_stats(date)
    
    # ==================== 规则引擎监控 ====================
    
    def record_rule_execution(
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
        return self.rule_detector.record_execution(
            stock_code=stock_code,
            is_timeout=is_timeout,
            is_error=is_error,
            score=score,
            verdict=verdict,
            execution_time=execution_time,
        )
    
    def get_rule_daily_stats(self, date: Optional[datetime] = None) -> dict:
        """
        获取规则引擎每日统计
        
        Args:
            date: 日期，默认今天
            
        Returns:
            每日统计数据
        """
        return self.rule_detector.get_daily_stats(date)
    
    # ==================== LLM幻觉监控 ====================
    
    def record_hallucination_confidence(
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
        return self.hallucination_detector.record_confidence(
            stock_code=stock_code,
            confidence_score=confidence_score,
            contradictions=contradictions,
            validation_details=validation_details,
        )
    
    def get_hallucination_daily_stats(self, date: Optional[datetime] = None) -> dict:
        """
        获取LLM幻觉每日统计
        
        Args:
            date: 日期，默认今天
            
        Returns:
            每日统计数据
        """
        return self.hallucination_detector.get_daily_stats(date)
    
    # ==================== 漂移检测 ====================
    
    def detect_locate_drift(self) -> List[DetectionResult]:
        """
        检测章节定位漂移
        
        Returns:
            检测结果列表
        """
        return self.locate_detector.detect()
    
    def detect_rule_drift(self) -> List[DetectionResult]:
        """
        检测规则引擎漂移
        
        Returns:
            检测结果列表
        """
        return self.rule_detector.detect()
    
    def detect_hallucination_drift(self) -> List[DetectionResult]:
        """
        检测LLM幻觉漂移
        
        Returns:
            检测结果列表
        """
        return self.hallucination_detector.detect()
    
    def detect_all(self) -> Dict[str, List[DetectionResult]]:
        """
        执行所有维度的漂移检测
        
        Returns:
            各维度的检测结果
        """
        results = {
            "chapter_locator": self.detect_locate_drift(),
            "redflag_engine": self.detect_rule_drift(),
            "llm_hallucination": self.detect_hallucination_drift(),
        }
        
        # 处理告警
        for dimension, detection_results in results.items():
            for result in detection_results:
                self.alert_manager.handle_detection_result(result)
                self._update_status(result)
        
        return results
    
    def _update_status(self, result: DetectionResult) -> None:
        """
        更新监控状态
        
        Args:
            result: 检测结果
        """
        dimension = result.dimension
        
        status = self._status.get(dimension, MonitorStatus(
            dimension=dimension,
            last_check_time=None,
            last_failure_rate=0.0,
            is_drift_detected=False,
            alert_count_today=0,
        ))
        
        status.last_check_time = datetime.now()
        status.last_failure_rate = result.failure_rate
        status.is_drift_detected = result.is_drift
        status.alert_count_today += 1 if result.is_drift else 0
        
        self._status[dimension] = status
    
    # ==================== 状态查询 ====================
    
    def get_status(self) -> DriftStatus:
        """
        获取当前漂移状态
        
        Returns:
            漂移状态汇总
        """
        # 获取各维度状态
        dimensions_status = {}
        
        for detector in get_all_detectors():
            dimension = detector.dimension
            stats = detector.get_daily_stats()
            
            status = self._status.get(dimension, MonitorStatus(
                dimension=dimension,
                last_check_time=None,
                last_failure_rate=stats.get("avg_value", 0.0),
                is_drift_detected=False,
                alert_count_today=0,
            ))
            
            dimensions_status[dimension.value] = status
        
        # 获取最近告警
        recent_alerts = self.db.get_alerts(limit=10)
        
        # 判断整体健康状态
        overall_healthy = not any(
            s.is_drift_detected for s in dimensions_status.values()
        )
        
        # 生成摘要
        drift_dimensions = [
            d for d, s in dimensions_status.items()
            if s.is_drift_detected
        ]
        
        if overall_healthy:
            summary = "系统运行正常，所有维度无漂移"
        else:
            summary = f"检测到漂移: {', '.join(drift_dimensions)}"
        
        return DriftStatus(
            timestamp=datetime.now(),
            overall_healthy=overall_healthy,
            dimensions=dimensions_status,
            recent_alerts=recent_alerts,
            summary=summary,
        )
    
    def get_dimension_status(self, dimension: DriftDimension) -> Optional[MonitorStatus]:
        """
        获取指定维度的状态
        
        Args:
            dimension: 漂移维度
            
        Returns:
            监控状态
        """
        return self._status.get(dimension)
    
    def get_drift_history(
        self,
        dimension: Optional[DriftDimension] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[DriftRecord]:
        """
        获取漂移历史
        
        Args:
            dimension: 漂移维度筛选
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量限制
            
        Returns:
            漂移记录列表
        """
        return self.db.get_drift_records(
            dimension=dimension,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    
    def get_alert_history(
        self,
        dimension: Optional[DriftDimension] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AlertRecord]:
        """
        获取告警历史
        
        Args:
            dimension: 漂移维度筛选
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量限制
            
        Returns:
            告警记录列表
        """
        return self.db.get_alerts(
            dimension=dimension,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    
    # ==================== 配置更新 ====================
    
    def update_threshold(
        self,
        dimension: DriftDimension,
        threshold: float,
    ) -> None:
        """
        更新阈值
        
        Args:
            dimension: 漂移维度
            threshold: 新的阈值
        """
        detection = self.config.detection
        
        if dimension == DriftDimension.CHAPTER_LOCATOR:
            detection.locate_failure_threshold = threshold
        elif dimension == DriftDimension.REDFLAG_ENGINE:
            detection.rule_error_threshold = threshold
        elif dimension == DriftDimension.LLM_HALLUCINATION:
            detection.hallucination_threshold = threshold
        
        logger.info(f"Updated threshold for {dimension.value}: {threshold}")


# 全局监控器实例
_monitor: Optional[DriftMonitor] = None


def get_drift_monitor(config: Optional[AppConfig] = None) -> DriftMonitor:
    """
    获取漂移监控器实例
    
    Args:
        config: 应用配置
        
    Returns:
        漂移监控器
    """
    global _monitor
    
    if _monitor is None:
        _monitor = DriftMonitor(config)
    
    return _monitor


def reset_drift_monitor() -> DriftMonitor:
    """
    重置漂移监控器
    
    Returns:
        新的监控器实例
    """
    global _monitor
    
    _monitor = None
    return get_drift_monitor()
