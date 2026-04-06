"""
漂移检测系统数据模型

定义漂移记录、告警记录及告警级别
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DriftDimension(str, Enum):
    """漂移检测维度"""
    CHAPTER_LOCATOR = "chapter_locator"
    REDFLAG_ENGINE = "redflag_engine"
    LLM_HALLUCINATION = "llm_hallucination"


class MetricType(str, Enum):
    """指标类型"""
    CONFIDENCE = "confidence"
    FAILURE_RATE = "failure_rate"
    TIMEOUT_RATE = "timeout_rate"
    ERROR_RATE = "error_rate"
    HALLUCINATION_SCORE = "hallucination_score"


@dataclass
class DriftRecord:
    """
    漂移记录 - 记录单次检测结果
    
    Attributes:
        id: 记录唯一标识
        stock_code: 股票代码
        dimension: 检测维度
        metric: 指标类型
        value: 指标值
        timestamp: 检测时间
        metadata: 附加元数据
    """
    id: Optional[int] = None
    stock_code: str = ""
    dimension: DriftDimension = DriftDimension.CHAPTER_LOCATOR
    metric: MetricType = MetricType.CONFIDENCE
    value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "stock_code": self.stock_code,
            "dimension": self.dimension.value,
            "metric": self.metric.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DriftRecord":
        """从字典创建"""
        return cls(
            id=data.get("id"),
            stock_code=data.get("stock_code", ""),
            dimension=DriftDimension(data.get("dimension", DriftDimension.CHAPTER_LOCATOR.value)),
            metric=MetricType(data.get("metric", MetricType.CONFIDENCE.value)),
            value=data.get("value", 0.0),
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else data.get("timestamp", datetime.now()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AlertRecord:
    """
    告警记录 - 触发告警时的记录
    
    Attributes:
        id: 告警唯一标识
        dimension: 漂移维度
        failure_rate: 失败率
        threshold: 阈值
        severity: 告警级别
        message: 告警消息
        created_at: 创建时间
        acknowledged: 是否已确认
    """
    id: Optional[int] = None
    dimension: DriftDimension = DriftDimension.CHAPTER_LOCATOR
    failure_rate: float = 0.0
    threshold: float = 0.0
    severity: AlertLevel = AlertLevel.INFO
    message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "dimension": self.dimension.value,
            "failure_rate": self.failure_rate,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AlertRecord":
        """从字典创建"""
        return cls(
            id=data.get("id"),
            dimension=DriftDimension(data.get("dimension", DriftDimension.CHAPTER_LOCATOR.value)),
            failure_rate=data.get("failure_rate", 0.0),
            threshold=data.get("threshold", 0.0),
            severity=AlertLevel(data.get("severity", AlertLevel.INFO.value)),
            message=data.get("message", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now()),
            acknowledged=data.get("acknowledged", False),
            metadata=data.get("metadata", {}),
        )
