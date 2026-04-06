"""
规则引擎漂移检测器 (Phase 3)

增强版规则引擎监控器：
1. 红旗比例异常监控（突然增加红灯）
2. 规则一致性检测（相同数据不同结果）
3. 使用SQLite记录漂移事件

Author: 架构师
Date: 2026-04-06
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import AppConfig, DetectionConfig, get_config
from .database import get_database
from .models import (
    AlertLevel,
    AlertRecord,
    DriftDimension,
    DriftRecord,
    MetricType,
)


# ============== 数据模型 ==============

@dataclass
class RuleExecutionRecord:
    """
    规则引擎执行记录
    
    用于追踪同一条数据的多次执行结果
    """
    id: Optional[int] = None
    stock_code: str = ""
    report_date: str = ""  # 财报日期/报告期
    data_hash: str = ""  # 输入数据哈希
    score: Optional[float] = None
    verdict: Optional[str] = None  # 红旗判定
    red_flag_count: int = 0  # 红旗数量
    execution_time: Optional[float] = None
    is_timeout: bool = False
    is_error: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


@dataclass
class ConsistencyCheckResult:
    """一致性检查结果"""
    is_consistent: bool
    stock_code: str
    report_date: str  # 修复：缺少此字段
    data_hash: str
    execution_count: int
    score_variance: float  # score方差
    verdict_conflicts: List[Tuple[Any, Any]]  # verdict冲突
    details: dict = field(default_factory=dict)


@dataclass
class RedFlagRatioStats:
    """红旗比例统计"""
    date: str
    total_count: int
    red_count: int
    yellow_count: int
    green_count: int
    red_ratio: float
    yellow_ratio: float
    green_ratio: float
    compared_to_yesterday: float = 0.0  # 与昨日相比变化


# ============== 规则引擎检测器 ==============

class RuleDriftDetectorEnhanced:
    """
    增强版规则引擎漂移检测器
    
    监控维度：
    1. 红旗比例异常 - 监控每日红旗比例，突然增加时触发告警
    2. 规则一致性 - 相同输入应产生相同输出，检测不一致情况
    
    使用SQLite存储漂移事件
    """
    
    dimension = DriftDimension.REDFLAG_ENGINE
    
    # 红旗比例变化阈值（超过此值触发告警）
    RED_RATIO_CHANGE_THRESHOLD = 0.15  # 15%
    
    # 一致性检测阈值
    SCORE_VARIANCE_THRESHOLD = 5.0  # score方差超过5分视为不一致
    
    def __init__(self, config: Optional[DetectionConfig] = None, db_path: str = "drift_detection.db"):
        """
        初始化检测器
        
        Args:
            config: 检测配置
            db_path: 数据库文件路径
        """
        if config is None:
            app_config = get_config()
            config = app_config.detection
        
        self.config = config
        self.db = get_database(db_path)
        self._init_rule_tables()
    
    def _init_rule_tables(self) -> None:
        """初始化规则引擎专用表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 规则执行记录表 - 用于一致性检测
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rule_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    data_hash TEXT NOT NULL,
                    score REAL,
                    verdict TEXT,
                    red_flag_count INTEGER DEFAULT 0,
                    execution_time REAL,
                    is_timeout INTEGER DEFAULT 0,
                    is_error INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # 确保旧数据库没有UNIQUE约束（修复用）
            try:
                cursor.execute("PRAGMA index_list('rule_executions')")
                indexes = cursor.fetchall()
                for idx in indexes:
                    if idx[2]:  # name
                        cursor.execute(f"DROP INDEX {idx[2]}")
            except:
                pass
            
            # 红旗比例历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS red_flag_ratios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    total_count INTEGER DEFAULT 0,
                    red_count INTEGER DEFAULT 0,
                    yellow_count INTEGER DEFAULT 0,
                    green_count INTEGER DEFAULT 0,
                    red_ratio REAL DEFAULT 0.0,
                    yellow_ratio REAL DEFAULT 0.0,
                    green_ratio REAL DEFAULT 0.0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rule_exec_stock_date 
                ON rule_executions(stock_code, report_date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rule_exec_hash 
                ON rule_executions(data_hash)
            """)
    
    @contextmanager
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ============== 记录方法 ==============
    
    def record_execution(
        self,
        stock_code: str,
        report_date: str,
        data_hash: str,
        score: Optional[float] = None,
        verdict: Optional[str] = None,
        red_flag_count: int = 0,
        execution_time: Optional[float] = None,
        is_timeout: bool = False,
        is_error: bool = False,
        metadata: dict = None,
    ) -> RuleExecutionRecord:
        """
        记录规则引擎执行结果
        
        Args:
            stock_code: 股票代码
            report_date: 报告期
            data_hash: 输入数据哈希
            score: 评分
            verdict: 红旗判定
            red_flag_count: 红旗数量
            execution_time: 执行时间(秒)
            is_timeout: 是否超时
            is_error: 是否异常
            metadata: 附加元数据
            
        Returns:
            执行记录
        """
        import hashlib
        
        # 计算数据哈希（如果未提供）
        if not data_hash:
            data_hash = hashlib.md5(
                f"{stock_code}:{report_date}".encode()
            ).hexdigest()
        
        record = RuleExecutionRecord(
            stock_code=stock_code,
            report_date=report_date,
            data_hash=data_hash,
            score=score,
            verdict=verdict,
            red_flag_count=red_flag_count,
            execution_time=execution_time,
            is_timeout=is_timeout,
            is_error=is_error,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )
        
        # 写入数据库（每次执行都插入，不使用唯一约束覆盖）
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO rule_executions 
                (stock_code, report_date, data_hash, score, verdict, 
                 red_flag_count, execution_time, is_timeout, is_error, 
                 timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.stock_code,
                    record.report_date,
                    record.data_hash,
                    record.score,
                    record.verdict,
                    record.red_flag_count,
                    record.execution_time,
                    1 if record.is_timeout else 0,
                    1 if record.is_error else 0,
                    record.timestamp.isoformat(),
                    json.dumps(record.metadata),
                ),
            )
            record.id = cursor.lastrowid
        
        # 同时写入通用漂移记录（用于每日聚合）
        self._record_to_drift_table(record)
        
        return record
    
    def _record_to_drift_table(self, record: RuleExecutionRecord) -> None:
        """将执行记录写入通用漂移记录表"""
        # 判断是否为异常
        is_anomaly = False
        
        # 检查超时
        if record.is_timeout or (
            record.execution_time and 
            record.execution_time > self.config.timeout_threshold
        ):
            is_anomaly = True
        
        # 检查score异常
        if record.score is not None:
            if record.score < 0 or record.score > 100:
                is_anomaly = True
        
        # 检查score/verdict不一致
        if record.score is not None and record.verdict is not None:
            expected_red = record.score >= self.config.red_flag_score_threshold
            actual_red = record.verdict.lower() in ["red", "存在", "有", "true", "1"]
            if expected_red != actual_red:
                is_anomaly = True
                metadata = {"inconsistency": True, "inconsistency_type": "score_verdict"}
            else:
                metadata = {}
        else:
            metadata = {}
        
        drift_record = DriftRecord(
            stock_code=record.stock_code,
            dimension=self.dimension,
            metric=MetricType.ERROR_RATE,
            value=1.0 if is_anomaly else 0.0,
            timestamp=record.timestamp,
            metadata=metadata,
        )
        
        self.db.create_drift_record(drift_record)
    
    # ============== 红旗比例监控 ==============
    
    def update_daily_red_flag_ratio(
        self,
        date: Optional[datetime] = None,
    ) -> RedFlagRatioStats:
        """
        更新每日红旗比例统计
        
        Args:
            date: 日期，默认今天
            
        Returns:
            红旗比例统计
        """
        date = date or datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 统计当日数据
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN verdict IN ('red', '存在', '有', 'true', '1') THEN 1 ELSE 0 END) as red_count,
                    SUM(CASE WHEN verdict IN ('yellow', 'yellow') THEN 1 ELSE 0 END) as yellow_count,
                    SUM(CASE WHEN verdict IN ('green', '无', 'none', '0') THEN 1 ELSE 0 END) as green_count
                FROM rule_executions
                WHERE date(timestamp) = ?
                """,
                (date_str,),
            )
            
            row = cursor.fetchone()
            total = row["total"] or 0
            red_count = row["red_count"] or 0
            yellow_count = row["yellow_count"] or 0
            green_count = row["green_count"] or 0
            
            if total == 0:
                return RedFlagRatioStats(
                    date=date_str,
                    total_count=0,
                    red_count=0,
                    yellow_count=0,
                    green_count=0,
                    red_ratio=0.0,
                    yellow_ratio=0.0,
                    green_ratio=0.0,
                )
            
            red_ratio = red_count / total
            yellow_ratio = yellow_count / total
            green_ratio = green_count / total
            
            # 获取昨日比例
            yesterday = (date - timedelta(days=1)).strftime("%Y-%m-%d")
            cursor.execute(
                "SELECT red_ratio FROM red_flag_ratios WHERE date = ?",
                (yesterday,),
            )
            yesterday_row = cursor.fetchone()
            compared_to_yesterday = red_ratio - (yesterday_row["red_ratio"] if yesterday_row else 0.0)
            
            stats = RedFlagRatioStats(
                date=date_str,
                total_count=total,
                red_count=red_count,
                yellow_count=yellow_count,
                green_count=green_count,
                red_ratio=red_ratio,
                yellow_ratio=yellow_ratio,
                green_ratio=green_ratio,
                compared_to_yesterday=compared_to_yesterday,
            )
            
            # 保存到数据库
            cursor.execute(
                """
                INSERT OR REPLACE INTO red_flag_ratios 
                (date, total_count, red_count, yellow_count, green_count, 
                 red_ratio, yellow_ratio, green_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stats.date,
                    stats.total_count,
                    stats.red_count,
                    stats.yellow_count,
                    stats.green_count,
                    stats.red_ratio,
                    stats.yellow_ratio,
                    stats.green_ratio,
                ),
            )
            
            return stats
    
    def check_red_flag_ratio_drift(
        self,
        date: Optional[datetime] = None,
    ) -> Optional[AlertRecord]:
        """
        检查红旗比例漂移
        
        Args:
            date: 日期，默认今天
            
        Returns:
            告警记录（无漂移返回None）
        """
        stats = self.update_daily_red_flag_ratio(date)
        
        if stats.total_count < 10:  # 样本太少不告警
            return None
        
        # 检查是否超过阈值
        if abs(stats.compared_to_yesterday) >= self.RED_RATIO_CHANGE_THRESHOLD:
            # 判断告警级别
            if stats.compared_to_yesterday > self.config.critical_threshold:
                severity = AlertLevel.CRITICAL
            elif stats.compared_to_yesterday > self.config.warning_threshold:
                severity = AlertLevel.WARNING
            else:
                severity = AlertLevel.INFO
            
            message = (
                f"红旗比例异常告警: 今日红旗比例 {stats.red_ratio:.2%}, "
                f"较昨日变化 {stats.compared_to_yesterday:+.2%}, "
                f"阈值 {self.RED_RATIO_CHANGE_THRESHOLD:.2%}"
            )
            
            alert = AlertRecord(
                dimension=self.dimension,
                failure_rate=stats.red_ratio,
                threshold=self.RED_RATIO_CHANGE_THRESHOLD,
                severity=severity,
                message=message,
                created_at=datetime.now(),
                metadata={
                    "date": stats.date,
                    "total_count": stats.total_count,
                    "red_count": stats.red_count,
                    "compared_to_yesterday": stats.compared_to_yesterday,
                    "alert_type": "red_flag_ratio_drift",
                },
            )
            
            alert.id = self.db.create_alert_record(alert)
            return alert
        
        return None
    
    # ============== 规则一致性检测 ==============
    
    def check_consistency(
        self,
        stock_code: str,
        report_date: str,
    ) -> ConsistencyCheckResult:
        """
        检查指定股票/报告期的一致性
        
        相同数据多次执行应该产生相同结果
        
        Args:
            stock_code: 股票代码
            report_date: 报告期
            
        Returns:
            一致性检查结果
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取该股票该报告期的所有执行记录
            cursor.execute(
                """
                SELECT * FROM rule_executions 
                WHERE stock_code = ? AND report_date = ?
                ORDER BY timestamp
                """,
                (stock_code, report_date),
            )
            
            rows = cursor.fetchall()
            
            if len(rows) <= 1:
                # 只有一条记录，无法比较一致性
                return ConsistencyCheckResult(
                    is_consistent=True,
                    stock_code=stock_code,
                    report_date=report_date,
                    data_hash="",
                    execution_count=len(rows),
                    score_variance=0.0,
                    verdict_conflicts=[],
                    details={"reason": "insufficient_data"},
                )
            
            # 收集score和verdict
            scores = [row["score"] for row in rows if row["score"] is not None]
            verdicts = [row["verdict"] for row in rows if row["verdict"] is not None]
            
            # 计算score方差
            score_variance = 0.0
            if len(scores) >= 2:
                mean_score = sum(scores) / len(scores)
                score_variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            
            # 检查verdict冲突
            verdict_conflicts = []
            unique_verdicts = set(verdicts)
            if len(unique_verdicts) > 1:
                # 存在不同 verdict
                verdict_conflicts = list(unique_verdicts)
            
            # 判断是否一致
            is_consistent = (
                score_variance < self.SCORE_VARIANCE_THRESHOLD and
                len(verdict_conflicts) == 0
            )
            
            return ConsistencyCheckResult(
                is_consistent=is_consistent,
                stock_code=stock_code,
                report_date=report_date,
                data_hash=rows[0]["data_hash"] if rows else "",
                execution_count=len(rows),
                score_variance=score_variance,
                verdict_conflicts=verdict_conflicts,
                details={
                    "scores": scores,
                    "verdicts": verdicts,
                    "mean_score": sum(scores) / len(scores) if scores else None,
                },
            )
    
    def detect_inconsistencies(
        self,
        days: int = 7,
    ) -> List[ConsistencyCheckResult]:
        """
        检测最近N天的不一致记录
        
        Args:
            days: 检测天数
            
        Returns:
            不一致记录列表
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取所有有重复执行的股票/报告期组合
            cursor.execute(
                """
                SELECT stock_code, report_date, COUNT(*) as cnt
                FROM rule_executions
                WHERE timestamp >= ?
                GROUP BY stock_code, report_date
                HAVING cnt > 1
                """,
                (cutoff_date,),
            )
            
            rows = cursor.fetchall()
            
            inconsistencies = []
            for row in rows:
                result = self.check_consistency(row["stock_code"], row["report_date"])
                if not result.is_consistent:
                    inconsistencies.append(result)
            
            return inconsistencies
    
    def record_consistency_alert(
        self,
        result: ConsistencyCheckResult,
    ) -> AlertRecord:
        """
        记录一致性告警
        
        Args:
            result: 一致性检查结果
            
        Returns:
            告警记录
        """
        severity = AlertLevel.WARNING
        
        if result.score_variance >= self.SCORE_VARIANCE_THRESHOLD * 2:
            severity = AlertLevel.CRITICAL
        
        message = (
            f"规则一致性告警: 股票 {result.stock_code} 报告期 {result.report_date} "
            f"执行{result.execution_count}次, score方差 {result.score_variance:.2f}, "
            f"verdict冲突: {result.verdict_conflicts}"
        )
        
        alert = AlertRecord(
            dimension=self.dimension,
            failure_rate=result.score_variance / 100.0,  # 归一化
            threshold=self.SCORE_VARIANCE_THRESHOLD / 100.0,
            severity=severity,
            message=message,
            created_at=datetime.now(),
            metadata={
                "stock_code": result.stock_code,
                "report_date": result.report_date,
                "execution_count": result.execution_count,
                "score_variance": result.score_variance,
                "verdict_conflicts": result.verdict_conflicts,
                "alert_type": "rule_consistency",
            },
        )
        
        alert.id = self.db.create_alert_record(alert)
        return alert
    
    # ============== 综合检测 ==============
    
    def detect(self) -> List[AlertRecord]:
        """
        执行漂移检测
        
        综合检测红旗比例漂移和规则一致性
        
        Returns:
            告警记录列表
        """
        alerts = []
        
        # 1. 检测红旗比例漂移
        ratio_alert = self.check_red_flag_ratio_drift()
        if ratio_alert:
            alerts.append(ratio_alert)
        
        # 2. 检测规则一致性
        inconsistencies = self.detect_inconsistencies(days=7)
        for result in inconsistencies:
            alert = self.record_consistency_alert(result)
            alerts.append(alert)
        
        return alerts
    
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


# ============== 兼容性包装器 ==============

class RuleDriftDetector:
    """
    规则引擎漂移检测器 - 兼容接口
    
    提供与原detectors.py中RuleDriftDetector兼容的接口
    """
    
    def __init__(self, config: Optional[DetectionConfig] = None):
        """初始化检测器"""
        if config is None:
            app_config = get_config()
            config = app_config.detection
        
        self.config = config
        self._enhanced = RuleDriftDetectorEnhanced(config, db_path=config.db_path)
    
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
        记录规则引擎执行结果（兼容接口）
        
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
        # 使用简化版data_hash（加入时间戳允许同股票多次记录）
        import hashlib
        timestamp = datetime.now().isoformat()
        data_hash = hashlib.md5(f"{stock_code}:{timestamp}".encode()).hexdigest()
        
        record = self._enhanced.record_execution(
            stock_code=stock_code,
            report_date=datetime.now().strftime("%Y-%m-%d"),
            data_hash=data_hash,
            score=score,
            verdict=verdict,
            execution_time=execution_time,
            is_timeout=is_timeout,
            is_error=is_error,
        )
        
        # 返回通用漂移记录
        return DriftRecord(
            id=record.id,
            stock_code=record.stock_code,
            dimension=self._enhanced.dimension,
            metric=MetricType.ERROR_RATE,
            value=1.0 if (is_timeout or is_error) else 0.0,
            timestamp=record.timestamp,
            metadata=record.metadata,
        )
    
    def detect(self) -> List[AlertRecord]:
        """
        执行漂移检测（兼容接口）
        """
        return self._enhanced.detect()
    
    def check_red_flag_ratio_drift(
        self,
        date: Optional[datetime] = None,
    ) -> Optional[AlertRecord]:
        """检查红旗比例漂移"""
        return self._enhanced.check_red_flag_ratio_drift(date)
    
    def check_consistency(
        self,
        stock_code: str,
        report_date: str,
    ) -> ConsistencyCheckResult:
        """检查规则一致性"""
        return self._enhanced.check_consistency(stock_code, report_date)
    
    def detect_inconsistencies(
        self,
        days: int = 7,
    ) -> List[ConsistencyCheckResult]:
        """检测最近N天的不一致记录"""
        return self._enhanced.detect_inconsistencies(days)
    
    def get_daily_stats(self, date: Optional[datetime] = None) -> dict:
        """获取每日统计"""
        return self._enhanced.get_daily_stats(date)


# 导入必要的模块
from contextlib import contextmanager