"""
漂移检测系统

监控A股分析系统的模型/管道性能退化
"""

from .config import (
    AppConfig,
    DetectionConfig,
    get_config,
    load_config,
    save_config,
    update_detection_config,
)
from .database import Database, get_database
from .detectors import (
    Detector,
    HallucinationDriftDetector,
    LocateDriftDetector,
    RuleDriftDetector,
    get_all_detectors,
    get_detector,
)
from .models import (
    AlertLevel,
    AlertRecord,
    DriftDimension,
    DriftRecord,
    MetricType,
)

__version__ = "1.0.0"

__all__ = [
    # 配置
    "AppConfig",
    "DetectionConfig",
    "get_config",
    "load_config",
    "save_config",
    "update_detection_config",
    # 数据库
    "Database",
    "get_database",
    # 数据模型
    "DriftRecord",
    "AlertRecord",
    "AlertLevel",
    "DriftDimension",
    "MetricType",
    # 检测器
    "Detector",
    "LocateDriftDetector",
    "RuleDriftDetector",
    "HallucinationDriftDetector",
    "get_detector",
    "get_all_detectors",
]
