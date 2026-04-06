"""
漂移检测系统配置管理

告警阈值配置和检测参数管理
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class DetectionConfig:
    """
    检测配置
    
    Attributes:
        # 章节定位配置
        confidence_threshold: 置信度阈值，低于此值视为失败
        locate_failure_threshold: 定位失败率阈值，超过此值告警
        
        # 规则引擎配置
        timeout_threshold: 超时阈值(秒)
        red_flag_score_threshold: 红旗评分阈值
        rule_error_threshold: 规则引擎错误率阈值
        
        # LLM幻觉配置
        hallucination_threshold: 幻觉率阈值
        
        # 告警级别配置
        warning_threshold: 警告阈值
        critical_threshold: 严重阈值
        
        # 数据库配置
        db_path: 数据库文件路径
        
        # 保留配置
        retention_days: 数据保留天数
    """
    # 章节定位
    confidence_threshold: float = 0.6
    locate_failure_threshold: float = 0.10
    
    # 规则引擎
    timeout_threshold: float = 180.0
    red_flag_score_threshold: float = 70.0
    rule_error_threshold: float = 0.10
    
    # LLM幻觉
    hallucination_threshold: float = 0.10
    
    # 告警级别
    warning_threshold: float = 0.10
    critical_threshold: float = 0.20
    
    # 数据库
    db_path: str = "drift_detection.db"
    
    # 保留
    retention_days: int = 90
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "confidence_threshold": self.confidence_threshold,
            "locate_failure_threshold": self.locate_failure_threshold,
            "timeout_threshold": self.timeout_threshold,
            "red_flag_score_threshold": self.red_flag_score_threshold,
            "rule_error_threshold": self.rule_error_threshold,
            "hallucination_threshold": self.hallucination_threshold,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "db_path": self.db_path,
            "retention_days": self.retention_days,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DetectionConfig":
        """从字典创建"""
        return cls(
            confidence_threshold=data.get("confidence_threshold", 0.6),
            locate_failure_threshold=data.get("locate_failure_threshold", 0.10),
            timeout_threshold=data.get("timeout_threshold", 180.0),
            red_flag_score_threshold=data.get("red_flag_score_threshold", 70.0),
            rule_error_threshold=data.get("rule_error_threshold", 0.10),
            hallucination_threshold=data.get("hallucination_threshold", 0.10),
            warning_threshold=data.get("warning_threshold", 0.10),
            critical_threshold=data.get("critical_threshold", 0.20),
            db_path=data.get("db_path", "drift_detection.db"),
            retention_days=data.get("retention_days", 90),
        )


@dataclass
class NotifierConfig:
    """
    通知配置
    
    Attributes:
        enabled: 是否启用
        webhook_url: Webhook URL
        webhook_enabled: Webhook是否启用
        email_enabled: 邮件是否启用
        email_recipients: 邮件接收者列表
        suppress_minutes: 告警抑制时间(分钟)
    """
    enabled: bool = True
    webhook_url: Optional[str] = None
    webhook_enabled: bool = False
    email_enabled: bool = False
    email_recipients: list = field(default_factory=list)
    suppress_minutes: int = 30


@dataclass
class AppConfig:
    """
    应用配置
    
    Attributes:
        detection: 检测配置
        notifier: 通知配置
    """
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    notifier: NotifierConfig = field(default_factory=NotifierConfig)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "detection": self.detection.to_dict(),
            "notifier": {
                "enabled": self.notifier.enabled,
                "webhook_url": self.notifier.webhook_url,
                "webhook_enabled": self.notifier.webhook_enabled,
                "email_enabled": self.notifier.email_enabled,
                "email_recipients": self.notifier.email_recipients,
                "suppress_minutes": self.notifier.suppress_minutes,
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """从字典创建"""
        return cls(
            detection=DetectionConfig.from_dict(data.get("detection", {})),
            notifier=NotifierConfig(
                enabled=data.get("notifier", {}).get("enabled", True),
                webhook_url=data.get("notifier", {}).get("webhook_url"),
                webhook_enabled=data.get("notifier", {}).get("webhook_enabled", False),
                email_enabled=data.get("notifier", {}).get("email_enabled", False),
                email_recipients=data.get("notifier", {}).get("email_recipients", []),
                suppress_minutes=data.get("notifier", {}).get("suppress_minutes", 30),
            ),
        )


# 全局配置实例
_config: Optional[AppConfig] = None
_config_path: Optional[str] = None


def get_config(config_path: Optional[str] = None) -> AppConfig:
    """
    获取配置（单例）
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        应用配置
    """
    global _config, _config_path
    
    # 如果指定了新的配置文件路径，重载配置
    if config_path and config_path != _config_path:
        _config = load_config(config_path)
        _config_path = config_path
    
    # 如果没有配置，加载默认配置
    if _config is None:
        _config = load_config(config_path) if config_path else AppConfig()
    
    return _config


def load_config(config_path: str) -> AppConfig:
    """
    从文件加载配置
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        应用配置
    """
    path = Path(config_path)
    
    if not path.exists():
        return AppConfig()
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppConfig.from_dict(data)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Warning: Failed to load config from {config_path}: {e}")
        return AppConfig()


def save_config(config: AppConfig, config_path: str) -> None:
    """
    保存配置到文件
    
    Args:
        config: 应用配置
        config_path: 配置文件路径
    """
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)


def update_detection_config(
    confidence_threshold: Optional[float] = None,
    locate_failure_threshold: Optional[float] = None,
    timeout_threshold: Optional[float] = None,
    red_flag_score_threshold: Optional[float] = None,
    rule_error_threshold: Optional[float] = None,
    hallucination_threshold: Optional[float] = None,
    warning_threshold: Optional[float] = None,
    critical_threshold: Optional[float] = None,
) -> AppConfig:
    """
    更新检测配置
    
    Args:
        confidence_threshold: 置信度阈值
        locate_failure_threshold: 定位失败率阈值
        timeout_threshold: 超时阈值
        red_flag_score_threshold: 红旗评分阈值
        rule_error_threshold: 规则引擎错误率阈值
        hallucination_threshold: 幻觉率阈值
        warning_threshold: 警告阈值
        critical_threshold: 严重阈值
        
    Returns:
        更新后的配置
    """
    config = get_config()
    detection = config.detection
    
    if confidence_threshold is not None:
        detection.confidence_threshold = confidence_threshold
    if locate_failure_threshold is not None:
        detection.locate_failure_threshold = locate_failure_threshold
    if timeout_threshold is not None:
        detection.timeout_threshold = timeout_threshold
    if red_flag_score_threshold is not None:
        detection.red_flag_score_threshold = red_flag_score_threshold
    if rule_error_threshold is not None:
        detection.rule_error_threshold = rule_error_threshold
    if hallucination_threshold is not None:
        detection.hallucination_threshold = hallucination_threshold
    if warning_threshold is not None:
        detection.warning_threshold = warning_threshold
    if critical_threshold is not None:
        detection.critical_threshold = critical_threshold
    
    return config


def get_default_config_path() -> str:
    """
    获取默认配置文件路径
    
    Returns:
        默认配置文件路径
    """
    return "config/drift_detection.json"


def reset_config() -> AppConfig:
    """
    重置为默认配置
    
    Returns:
        默认配置
    """
    global _config, _config_path
    _config = AppConfig()
    _config_path = None
    return _config
