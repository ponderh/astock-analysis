"""
漂移检测告警系统

支持P0-P3四级告警、日志记录、告警抑制(冷却期机制)
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Callable, Dict, List, Optional

from .config import AppConfig, NotifierConfig, get_config
from .database import get_database
from .models import AlertLevel, AlertRecord, DriftDimension

# 配置日志
logger = logging.getLogger(__name__)


class AlertPriority(str, Enum):
    """告警优先级 P0-P3"""
    P0_CRITICAL = "P0"  # 严重：需要立即处理
    P1_HIGH = "P1"      # 高：需要尽快处理
    P2_MEDIUM = "P2"    # 中：需要关注
    P3_LOW = "P3"       # 低：信息性告警


# 告警级别到优先级的映射
ALERT_LEVEL_TO_PRIORITY = {
    AlertLevel.CRITICAL: AlertPriority.P0_CRITICAL,
    AlertLevel.WARNING: AlertPriority.P1_HIGH,
    AlertLevel.INFO: AlertPriority.P2_MEDIUM,
}


@dataclass
class AlertEvent:
    """告警事件"""
    alert_id: str
    dimension: DriftDimension
    priority: AlertPriority
    level: AlertLevel
    message: str
    failure_rate: float
    threshold: float
    created_at: datetime
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "dimension": self.dimension.value,
            "priority": self.priority.value,
            "level": self.level.value,
            "message": self.message,
            "failure_rate": self.failure_rate,
            "threshold": self.threshold,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class AlertLogger:
    """告警日志记录器"""
    
    def __init__(self, log_file: Optional[str] = None):
        """
        初始化日志记录器
        
        Args:
            log_file: 日志文件路径，默认为alerts.log
        """
        self.log_file = log_file or "drift_alerts.log"
        self._setup_logger()
    
    def _setup_logger(self):
        """配置日志记录器"""
        self.logger = logging.getLogger("drift_alerts")
        self.logger.setLevel(logging.INFO)
        
        # 文件处理器
        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 格式化
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def log_alert(self, event: AlertEvent) -> None:
        """
        记录告警事件
        
        Args:
            event: 告警事件
        """
        priority_emoji = {
            AlertPriority.P0_CRITICAL: "🔴",
            AlertPriority.P1_HIGH: "🟠",
            AlertPriority.P2_MEDIUM: "🟡",
            AlertPriority.P3_LOW: "🔵",
        }
        
        emoji = priority_emoji.get(event.priority, "⚪")
        
        log_message = (
            f"{emoji} [{event.priority.value}] {event.dimension.value} - "
            f"失败率: {event.failure_rate:.2%} (阈值: {event.threshold:.2%}) - "
            f"{event.message}"
        )
        
        if event.level == AlertLevel.CRITICAL:
            self.logger.error(log_message)
        elif event.level == AlertLevel.WARNING:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def log_alert_suppressed(self, event: AlertEvent, cooldown_remaining: float) -> None:
        """
        记录被抑制的告警
        
        Args:
            event: 告警事件
            cooldown_remaining: 剩余冷却时间(秒)
        """
        self.logger.info(
            f"⏸️ [Suppressed] {event.dimension.value} - "
            f"冷却中 ({cooldown_remaining:.0f}s remaining) - {event.message}"
        )


class AlertSuppressor:
    """告警抑制器 - 冷却期机制"""
    
    def __init__(self, cooldown_seconds: int = 1800):
        """
        初始化抑制器
        
        Args:
            cooldown_seconds: 冷却时间(秒)，默认30分钟
        """
        self.cooldown_seconds = cooldown_seconds
        self._last_alert_time: Dict[str, datetime] = {}
        self._lock = Lock()
    
    def should_send(self, dimension: DriftDimension, priority: AlertPriority) -> bool:
        """
        检查是否应该发送告警
        
        Args:
            dimension: 漂移维度
            priority: 告警优先级
            
        Returns:
            是否应该发送告警
        """
        key = f"{dimension.value}:{priority.value}"
        
        with self._lock:
            last_time = self._last_alert_time.get(key)
            
            if last_time is None:
                return True
            
            elapsed = (datetime.now() - last_time).total_seconds()
            
            # 优先级越高，冷却时间越短
            cooldown = self._get_priority_cooldown(priority)
            
            if elapsed < cooldown:
                return False
            
            return True
    
    def record_alert(self, dimension: DriftDimension, priority: AlertPriority) -> None:
        """
        记录告警发送时间
        
        Args:
            dimension: 漂移维度
            priority: 告警优先级
        """
        key = f"{dimension.value}:{priority.value}"
        
        with self._lock:
            self._last_alert_time[key] = datetime.now()
    
    def get_cooldown_remaining(self, dimension: DriftDimension, priority: AlertPriority) -> float:
        """
        获取剩余冷却时间
        
        Args:
            dimension: 漂移维度
            priority: 告警优先级
            
        Returns:
            剩余冷却时间(秒)
        """
        key = f"{dimension.value}:{priority.value}"
        
        with self._lock:
            last_time = self._last_alert_time.get(key)
            
            if last_time is None:
                return 0.0
            
            elapsed = (datetime.now() - last_time).total_seconds()
            cooldown = self._get_priority_cooldown(priority)
            
            return max(0.0, cooldown - elapsed)
    
    def _get_priority_cooldown(self, priority: AlertPriority) -> float:
        """
        根据优先级获取冷却时间
        
        Args:
            priority: 告警优先级
            
        Returns:
            冷却时间(秒)
        """
        # P0: 10分钟, P1: 20分钟, P2: 30分钟, P3: 60分钟
        priority_cooldown = {
            AlertPriority.P0_CRITICAL: 600,
            AlertPriority.P1_HIGH: 1200,
            AlertPriority.P2_MEDIUM: 1800,
            AlertPriority.P3_LOW: 3600,
        }
        
        return priority_cooldown.get(priority, self.cooldown_seconds)
    
    def clear(self) -> None:
        """清除所有冷却状态"""
        with self._lock:
            self._last_alert_time.clear()


class WebhookNotifier:
    """Webhook通知器"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        初始化Webhook通知器
        
        Args:
            webhook_url: Webhook URL
        """
        self.webhook_url = webhook_url
    
    async def send(self, event: AlertEvent) -> bool:
        """
        发送告警到Webhook
        
        Args:
            event: 告警事件
            
        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            logger.debug("Webhook not configured, skipping")
            return False
        
        try:
            import aiohttp
            
            payload = {
                "alert_id": event.alert_id,
                "dimension": event.dimension.value,
                "priority": event.priority.value,
                "level": event.level.value,
                "message": event.message,
                "failure_rate": event.failure_rate,
                "threshold": event.threshold,
                "timestamp": event.created_at.isoformat(),
                "metadata": event.metadata,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        logger.info(f"Webhook alert sent: {event.alert_id}")
                        return True
                    else:
                        logger.error(f"Webhook failed: {response.status}")
                        return False
        
        except ImportError:
            logger.warning("aiohttp not installed, webhook disabled")
            return False
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return False
    
    def send_sync(self, event: AlertEvent) -> bool:
        """
        同步发送告警到Webhook
        
        Args:
            event: 告警事件
            
        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            return False
        
        try:
            import requests
            
            payload = {
                "alert_id": event.alert_id,
                "dimension": event.dimension.value,
                "priority": event.priority.value,
                "level": event.level.value,
                "message": event.message,
                "failure_rate": event.failure_rate,
                "threshold": event.threshold,
                "timestamp": event.created_at.isoformat(),
                "metadata": event.metadata,
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            
            return response.status_code == 200
        
        except ImportError:
            logger.warning("requests not installed, webhook disabled")
            return False
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return False


class AlertManager:
    """
    告警管理器
    
    整合日志记录、告警抑制、Webhook通知
    支持P0-P3四级告警
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        初始化告警管理器
        
        Args:
            config: 应用配置
        """
        self.config = config or get_config()
        self.notifier_config = self.config.notifier
        
        # 初始化组件
        self.logger = AlertLogger()
        self.suppressor = AlertSuppressor(
            cooldown_seconds=self.notifier_config.suppress_minutes * 60
        )
        self.webhook = WebhookNotifier(
            webhook_url=self.notifier_config.webhook_url
        ) if self.notifier_config.webhook_enabled else None
        
        # 回调函数
        self._callbacks: List[Callable[[AlertEvent], None]] = []
        
        logger.info(f"AlertManager initialized with suppress_minutes={self.notifier_config.suppress_minutes}")
    
    def register_callback(self, callback: Callable[[AlertEvent], None]) -> None:
        """
        注册告警回调
        
        Args:
            callback: 回调函数，接收AlertEvent参数
        """
        self._callbacks.append(callback)
    
    def handle_alert(
        self,
        dimension: DriftDimension,
        level: AlertLevel,
        message: str,
        failure_rate: float,
        threshold: float,
        metadata: dict = None,
    ) -> Optional[AlertEvent]:
        """
        处理告警
        
        Args:
            dimension: 漂移维度
            level: 告警级别
            message: 告警消息
            failure_rate: 失败率
            threshold: 阈值
            metadata: 附加元数据
            
        Returns:
            如果触发告警返回AlertEvent，否则返回None
        """
        # 检查是否启用
        if not self.notifier_config.enabled:
            logger.debug("Alerts disabled, skipping")
            return None
        
        # 转换级别到优先级
        priority = ALERT_LEVEL_TO_PRIORITY.get(level, AlertPriority.P3_LOW)
        
        # 优先处理P0，不受抑制
        if priority != AlertPriority.P0_CRITICAL:
            # 检查是否应该发送
            if not self.suppressor.should_send(dimension, priority):
                cooldown = self.suppressor.get_cooldown_remaining(dimension, priority)
                
                # 记录被抑制的告警
                suppressed_event = AlertEvent(
                    alert_id="",
                    dimension=dimension,
                    priority=priority,
                    level=level,
                    message=message,
                    failure_rate=failure_rate,
                    threshold=threshold,
                    created_at=datetime.now(),
                    metadata=metadata or {},
                )
                self.logger.log_alert_suppressed(suppressed_event, cooldown)
                return None
        
        # 创建告警事件
        event = AlertEvent(
            alert_id=str(uuid.uuid4())[:8],
            dimension=dimension,
            priority=priority,
            level=level,
            message=message,
            failure_rate=failure_rate,
            threshold=threshold,
            created_at=datetime.now(),
            metadata=metadata or {},
        )
        
        # 记录日志
        self.logger.log_alert(event)
        
        # 记录发送时间(用于抑制)
        self.suppressor.record_alert(dimension, priority)
        
        # 发送Webhook
        if self.webhook and self.notifier_config.webhook_enabled:
            try:
                self.webhook.send_sync(event)
            except Exception as e:
                logger.error(f"Failed to send webhook: {e}")
        
        # 保存告警记录到数据库
        try:
            db = get_database(self.config.detection.db_path)
            alert_record = AlertRecord(
                dimension=event.dimension,
                failure_rate=event.failure_rate,
                threshold=event.threshold,
                severity=event.level,
                message=event.message,
                created_at=event.created_at,
                metadata=event.metadata,
            )
            alert_record.id = db.create_alert_record(alert_record)
            logger.debug(f"Alert record saved: {alert_record.id}")
        except Exception as e:
            logger.error(f"Failed to save alert record: {e}")
        
        # 执行回调
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        return event
    
    def handle_detection_result(self, result) -> Optional[AlertEvent]:
        """
        处理检测结果
        
        Args:
            result: DetectionResult from detector
            
        Returns:
            如果触发告警返回AlertEvent，否则返回None
        """
        if not result.is_drift:
            return None
        
        return self.handle_alert(
            dimension=result.dimension,
            level=result.severity,
            message=result.message,
            failure_rate=result.failure_rate,
            threshold=result.threshold,
            metadata=result.metadata,
        )
    
    def get_suppressed_dimensions(self) -> List[dict]:
        """
        获取当前处于抑制状态的维度
        
        Returns:
            抑制状态列表
        """
        suppressed = []
        
        for dimension in DriftDimension:
            for priority in AlertPriority:
                remaining = self.suppressor.get_cooldown_remaining(dimension, priority)
                if remaining > 0:
                    suppressed.append({
                        "dimension": dimension.value,
                        "priority": priority.value,
                        "remaining_seconds": remaining,
                    })
        
        return suppressed
    
    def clear_suppression(self) -> None:
        """清除所有抑制状态"""
        self.suppressor.clear()
        logger.info("Alert suppression cleared")


# 全局告警管理器
_alert_manager: Optional[AlertManager] = None


def get_alert_manager(config: Optional[AppConfig] = None) -> AlertManager:
    """
    获取告警管理器实例
    
    Args:
        config: 应用配置
        
    Returns:
        告警管理器
    """
    global _alert_manager
    
    if _alert_manager is None:
        _alert_manager = AlertManager(config)
    
    return _alert_manager


def reset_alert_manager() -> AlertManager:
    """
    重置告警管理器
    
    Returns:
        新的告警管理器实例
    """
    global _alert_manager
    
    _alert_manager = None
    return get_alert_manager()
