"""
章节定位漂移检测器 (LocateDriftDetector)

监控MD&A章节定位成功率，置信度 < 0.6 视为失败并记录漂移事件

Phase 2 交付物：
1. 实现章节定位监控器 LocateDriftDetector
2. 统计过去N次分析的定位成功率
3. 置信度低于阈值（0.6）时记录漂移
4. 使用SQLite记录漂移事件
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from .config import DetectionConfig, get_config
from .database import Database, get_database
from .models import (
    AlertLevel,
    AlertRecord,
    DriftDimension,
    DriftRecord,
    MetricType,
)


@dataclass
class DailyStats:
    """每日定位统计"""
    date: datetime
    total_count: int = 0          # 总定位次数
    success_count: int = 0       # 成功次数
    failure_count: int = 0       # 失败次数
    success_rate: float = 0.0    # 成功率
    failure_rate: float = 0.0    # 失败率
    avg_confidence: float = 0.0  # 平均置信度
    min_confidence: float = 0.0    # 最低置信度
    max_confidence: float = 0.0   # 最高置信度
    
    def to_dict(self) -> dict:
        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "avg_confidence": self.avg_confidence,
            "min_confidence": self.min_confidence,
            "max_confidence": self.max_confidence,
        }


class LocateDriftDetector:
    """
    章节定位漂移检测器
    
    监控MD&A章节定位成功率，当置信度 < 阈值(0.6)时记录漂移事件。
    
    Usage:
        detector = LocateDriftDetector()
        
        # 记录单次定位结果
        detector.record("000001", 0.85)  # 成功
        detector.record("000001", 0.45)  # 失败
        
        # 获取每日统计
        stats = detector.get_daily_stats()
        
        # 获取成功率趋势(过去N天)
        trend = detector.get_success_rate_trend(days=7)
        
        # 检查是否需要告警
        alerts = detector.check_drift()
    """
    
    # 维度标识
    DIMENSION = DriftDimension.CHAPTER_LOCATOR
    
    # 默认置信度阈值
    DEFAULT_CONFIDENCE_THRESHOLD = 0.6
    
    # 默认失败率告警阈值
    DEFAULT_FAILURE_RATE_THRESHOLD = 0.10
    
    def __init__(
        self,
        db: Optional[Database] = None,
        config: Optional[DetectionConfig] = None,
    ):
        """
        初始化检测器
        
        Args:
            db: 数据库实例
            config: 检测配置
        """
        self._db = db
        self._config = config
    
    @property
    def db(self) -> Database:
        """获取数据库实例"""
        if self._db is None:
            self._db = get_database()
        return self._db
    
    @property
    def config(self) -> DetectionConfig:
        """获取检测配置"""
        if self._config is None:
            self._config = get_config().detection
        return self._config
    
    @property
    def confidence_threshold(self) -> float:
        """获取置信度阈值"""
        return self.config.confidence_threshold
    
    @property
    def failure_threshold(self) -> float:
        """获取失败率��警阈值"""
        return self.config.locate_failure_threshold
    
    def record(
        self,
        stock_code: str,
        confidence: float,
        timestamp: Optional[datetime] = None,
        metadata: Optional[dict] = None,
    ) -> DriftRecord:
        """
        记录单次章节定位结果
        
        当置信度 < 阈值(0.6)时，记录为失败并标记为漂移事件。
        
        Args:
            stock_code: 股票代码
            confidence: 定位置信度 [0.0, 1.0]
            timestamp: 检测时间(默认当前时间)
            metadata: 附加元数据
            
        Returns:
            漂移记录
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if metadata is None:
            metadata = {}
        
        # 判断是否失败
        is_failure = confidence < self.confidence_threshold
        
        # 构建元数据
        record_metadata = {
            "confidence": confidence,
            "is_failure": is_failure,
            "threshold": self.confidence_threshold,
            **metadata,
        }
        
        # 创建漂移记录
        record = DriftRecord(
            stock_code=stock_code,
            dimension=self.DIMENSION,
            metric=MetricType.CONFIDENCE,
            value=confidence,
            timestamp=timestamp,
            metadata=record_metadata,
        )
        
        # 保存到数据库
        record.id = self.db.create_drift_record(record)
        
        return record
    
    def record_batch(
        self,
        records: List[Tuple[str, float]],
        base_timestamp: Optional[datetime] = None,
    ) -> List[DriftRecord]:
        """
        批量记录定位结果
        
        Args:
            records: [(stock_code, confidence), ...]
            base_timestamp: 基准时间(用于批量插入)
            
        Returns:
            漂移记录列表
        """
        if base_timestamp is None:
            base_timestamp = datetime.now()
        
        result = []
        for i, (stock_code, confidence) in enumerate(records):
            # 每个记录间隔1秒
            timestamp = base_timestamp + timedelta(seconds=i)
            record = self.record(stock_code, confidence, timestamp)
            result.append(record)
        
        return result
    
    def get_daily_stats(
        self,
        date: Optional[datetime] = None,
    ) -> DailyStats:
        """
        获取每日定位统计
        
        Args:
            date: 日期(默认今天)
            
        Returns:
            每日统计数据
        """
        if date is None:
            date = datetime.now()
        
        # 查询当天的所有定位记录
        records = self.db.get_drift_records(
            dimension=self.DIMENSION,
            start_time=datetime(date.year, date.month, date.day),
            end_time=datetime(date.year, date.month, date.day, 23, 59, 59),
            limit=10000,
        )
        
        if not records:
            return DailyStats(date=date)
        
        # 统计
        total_count = len(records)
        success_records = [r for r in records if r.value >= self.confidence_threshold]
        failure_records = [r for r in records if r.value < self.confidence_threshold]
        
        success_count = len(success_records)
        failure_count = len(failure_records)
        
        success_rate = success_count / total_count if total_count > 0 else 0.0
        failure_rate = failure_count / total_count if total_count > 0 else 0.0
        
        confidences = [r.value for r in records]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        min_confidence = min(confidences) if confidences else 0.0
        max_confidence = max(confidences) if confidences else 0.0
        
        return DailyStats(
            date=date,
            total_count=total_count,
            success_count=success_count,
            failure_count=failure_count,
            success_rate=success_rate,
            failure_rate=failure_rate,
            avg_confidence=avg_confidence,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
        )
    
    def get_success_rate_trend(
        self,
        days: int = 7,
        end_date: Optional[datetime] = None,
    ) -> List[DailyStats]:
        """
        获取过去N天的成功率趋势
        
        Args:
            days: 天数
            end_date: 结束日期(默认今天)
            
        Returns:
            每日统计数据列表
        """
        if end_date is None:
            end_date = datetime.now()
        
        # 计算开始日期
        start_date = end_date - timedelta(days=days - 1)
        
        result = []
        current = start_date
        while current <= end_date:
            stats = self.get_daily_stats(current)
            result.append(stats)
            current += timedelta(days=1)
        
        return result
    
    def get_recent_records(
        self,
        stock_code: Optional[str] = None,
        limit: int = 100,
    ) -> List[DriftRecord]:
        """
        获取最近的定位记录
        
        Args:
            stock_code: 股票代码过滤(可选)
            limit: 返回数量
            
        Returns:
            漂移记录列表
        """
        return self.db.get_drift_records(
            dimension=self.DIMENSION,
            stock_code=stock_code,
            limit=limit,
        )
    
    def get_success_rate(
        self,
        stock_code: str,
        limit: int = 100,
    ) -> Tuple[float, int]:
        """
        获取指定股票的历史定位成功率
        
        Args:
            stock_code: 股票代码
            limit: 统计样本数
            
        Returns:
            (成功率, 样本数)
        """
        records = self.db.get_drift_records(
            dimension=self.DIMENSION,
            stock_code=stock_code,
            limit=limit,
        )
        
        if not records:
            return 0.0, 0
        
        success_count = sum(1 for r in records if r.value >= self.confidence_threshold)
        return success_count / len(records), len(records)
    
    def check_drift(
        self,
        date: Optional[datetime] = None,
    ) -> List[AlertRecord]:
        """
        检查是否发生漂移并触发告警
        
        当失败率超过阈值时生成告警记录。
        
        Args:
            date: 检查日期(默认今天)
            
        Returns:
            告警记录列表
        """
        if date is None:
            date = datetime.now()
        
        # 获取每日统计
        stats = self.get_daily_stats(date)
        
        # 检查是否超过阈值
        if stats.failure_rate >= self.failure_threshold:
            # 确定告警级别
            if stats.failure_rate >= self.config.critical_threshold:
                severity = AlertLevel.CRITICAL
            elif stats.failure_rate >= self.config.warning_threshold:
                severity = AlertLevel.WARNING
            else:
                severity = AlertLevel.INFO
            
            # 构建告警消息
            message = (
                f"章节定位漂移告警: "
                f"失败率 {stats.failure_rate:.1%} "
                f"超过阈值 {self.failure_threshold:.1%} "
                f"(总计 {stats.total_count} 次定位，"
                f"失败 {stats.failure_count} 次)"
            )
            
            # 创建告警记录
            alert = AlertRecord(
                dimension=self.DIMENSION,
                failure_rate=stats.failure_rate,
                threshold=self.failure_threshold,
                severity=severity,
                message=message,
                created_at=datetime.now(),
                metadata=stats.to_dict(),
            )
            
            # 保存告警
            alert.id = self.db.create_alert_record(alert)
            
            return [alert]
        
        return []
    
    def get_latest_alerts(
        self,
        limit: int = 10,
    ) -> List[AlertRecord]:
        """
        获取最近的告警记录
        
        Args:
            limit: 返回数量
            
        Returns:
            告警记录列表
        """
        return self.db.get_alert_records(
            dimension=self.DIMENSION,
            limit=limit,
        )


# 全局检测器实例
_detector: Optional[LocateDriftDetector] = None


def get_detector(db_path: str = "drift_detection.db") -> LocateDriftDetector:
    """
    获取LocateDriftDetector实例(单例)
    
    Args:
        db_path: 数据库文件路径
        
    Returns:
        检测器实例
    """
    global _detector
    if _detector is None:
        db = get_database(db_path)
        _detector = LocateDriftDetector(db=db)
    return _detector


# ========== 便捷函数 ==========

def record_locate_result(
    stock_code: str,
    confidence: float,
    timestamp: Optional[datetime] = None,
) -> DriftRecord:
    """
    记录章节定位结果(便捷函数)
    
    Args:
        stock_code: 股票代码
        confidence: 置信度
        timestamp: 时间
        
    Returns:
        漂移记录
    """
    detector = get_detector()
    return detector.record(stock_code, confidence, timestamp)


def get_locate_stats(days: int = 7) -> List[DailyStats]:
    """
    获取定位成功率趋势(便捷函数)
    
    Args:
        days: 天数
        
    Returns:
        每日统计列表
    """
    detector = get_detector()
    return detector.get_success_rate_trend(days=days)


def check_locate_drift(date: Optional[datetime] = None) -> List[AlertRecord]:
    """
    检查章节定位漂移(便捷函数)
    
    Args:
        date: 日期
        
    Returns:
        告警列表
    """
    detector = get_detector()
    return detector.check_drift(date)