"""
漂移检测系统数据库层

SQLite数据库Schema定义和CRUD操作
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, List, Optional

from .models import AlertLevel, AlertRecord, DriftDimension, DriftRecord, MetricType


class Database:
    """SQLite数据库管理器"""
    
    def __init__(self, db_path: str = "drift_detection.db"):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """获取数据库连接上下文"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self) -> None:
        """初始化数据库表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 漂移记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drift_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 告警记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dimension TEXT NOT NULL,
                    failure_rate REAL NOT NULL,
                    threshold REAL NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    acknowledged INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_drift_stock_code 
                ON drift_records(stock_code)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_drift_dimension 
                ON drift_records(dimension)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_drift_timestamp 
                ON drift_records(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_created_at 
                ON alert_records(created_at)
            """)
    
    # ========== DriftRecord CRUD ==========
    
    def create_drift_record(self, record: DriftRecord) -> int:
        """
        创建漂移记录
        
        Args:
            record: 漂移记录
            
        Returns:
            新记录的ID
        """
        import json
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO drift_records 
                (stock_code, dimension, metric, value, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.stock_code,
                    record.dimension.value,
                    record.metric.value,
                    record.value,
                    record.timestamp.isoformat(),
                    json.dumps(record.metadata),
                ),
            )
            return cursor.lastrowid
    
    def get_drift_records(
        self,
        dimension: Optional[DriftDimension] = None,
        stock_code: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[DriftRecord]:
        """
        查询漂移记录
        
        Args:
            dimension: 漂移维度过滤
            stock_code: 股票代码过滤
            start_time: 开始时间(兼容)
            end_time: 结束时间(兼容)
            start_date: 开始日期(兼容)
            end_date: 结束日期(兼容)
            limit: 返回数量限制
            
        Returns:
            漂移记录列表
        """
        # 兼容 start_date/end_date 参数
        start_time = start_time or start_date
        end_time = end_time or end_date
        
        import json
        
        query = "SELECT * FROM drift_records WHERE 1=1"
        params = []
        
        if dimension:
            query += " AND dimension = ?"
            params.append(dimension.value)
        
        if stock_code:
            query += " AND stock_code = ?"
            params.append(stock_code)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                DriftRecord(
                    id=row["id"],
                    stock_code=row["stock_code"],
                    dimension=DriftDimension(row["dimension"]),
                    metric=MetricType(row["metric"]),
                    value=row["value"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    metadata=json.loads(row["metadata"]),
                )
                for row in rows
            ]
    
    def get_daily_stats(
        self,
        dimension: DriftDimension,
        date: datetime,
    ) -> dict:
        """
        获取每日统计
        
        Args:
            dimension: 漂移维度
            date: 日期
            
        Returns:
            每日统计数据
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            date_str = date.strftime("%Y-%m-%d")
            
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_count,
                    AVG(value) as avg_value,
                    MIN(value) as min_value,
                    MAX(value) as max_value
                FROM drift_records
                WHERE dimension = ? 
                AND timestamp >= ? 
                AND timestamp < ?
                """,
                (dimension.value, date_str, f"{date_str}T23:59:59"),
            )
            
            row = cursor.fetchone()
            return {
                "total_count": row["total_count"] or 0,
                "avg_value": row["avg_value"] or 0.0,
                "min_value": row["min_value"] or 0.0,
                "max_value": row["max_value"] or 0.0,
            }
    
    # ========== AlertRecord CRUD ==========
    
    def create_alert_record(self, record: AlertRecord) -> int:
        """
        创建告警记录
        
        Args:
            record: 告警记录
            
        Returns:
            新记录的ID
        """
        import json
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO alert_records 
                (dimension, failure_rate, threshold, severity, message, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.dimension.value,
                    record.failure_rate,
                    record.threshold,
                    record.severity.value,
                    record.message,
                    record.created_at.isoformat(),
                    json.dumps(record.metadata),
                ),
            )
            return cursor.lastrowid
    
    def get_alert_records(
        self,
        dimension: Optional[DriftDimension] = None,
        severity: Optional[AlertLevel] = None,
        acknowledged: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AlertRecord]:
        """
        查询告警记录
        
        Args:
            dimension: 漂移维度过滤
            severity: 告警级别过滤
            acknowledged: 已确认过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            
        Returns:
            告警记录列表
        """
        import json
        
        query = "SELECT * FROM alert_records WHERE 1=1"
        params = []
        
        if dimension:
            query += " AND dimension = ?"
            params.append(dimension.value)
        
        if severity:
            query += " AND severity = ?"
            params.append(severity.value)
        
        if acknowledged is not None:
            query += " AND acknowledged = ?"
            params.append(1 if acknowledged else 0)
        
        if start_time:
            query += " AND created_at >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            query += " AND created_at <= ?"
            params.append(end_time.isoformat())
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                AlertRecord(
                    id=row["id"],
                    dimension=DriftDimension(row["dimension"]),
                    failure_rate=row["failure_rate"],
                    threshold=row["threshold"],
                    severity=AlertLevel(row["severity"]),
                    message=row["message"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    acknowledged=bool(row["acknowledged"]),
                    metadata=json.loads(row["metadata"]),
                )
                for row in rows
            ]
    
    def get_alerts(
        self,
        dimension: Optional[DriftDimension] = None,
        severity: Optional[AlertLevel] = None,
        acknowledged: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AlertRecord]:
        """
        查询告警记录（兼容接口）
        
        Args:
            dimension: 漂移维度过滤
            severity: 告警级别过滤
            acknowledged: 已确认过滤
            start_date: 开始时间
            end_date: 结束时间
            limit: 返回数量限制
            
        Returns:
            告警记录列表
        """
        return self.get_alert_records(
            dimension=dimension,
            severity=severity,
            acknowledged=acknowledged,
            start_time=start_date,
            end_time=end_date,
            limit=limit,
        )

    def acknowledge_alert(self, alert_id: int) -> bool:
        """
        确认告警
        
        Args:
            alert_id: 告警ID
            
        Returns:
            是否成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE alert_records SET acknowledged = 1 WHERE id = ?",
                (alert_id,),
            )
            return cursor.rowcount > 0
    
    # ========== 工具方法 ==========
    
    def cleanup_old_records(self, days: int = 90) -> int:
        """
        清理旧记录
        
        Args:
            days: 保留天数
            
        Returns:
            删除的记录数
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 删除旧漂移记录
            cursor.execute(
                "DELETE FROM drift_records WHERE timestamp < ?",
                (cutoff.isoformat(),),
            )
            drift_count = cursor.rowcount
            
            # 删除旧告警记录
            cursor.execute(
                "DELETE FROM alert_records WHERE created_at < ?",
                (cutoff.isoformat(),),
            )
            alert_count = cursor.rowcount
            
            return drift_count + alert_count


# 全局数据库实例
_db: Optional[Database] = None


def get_database(db_path: str = "drift_detection.db") -> Database:
    """
    获取数据库实例（单例）
    
    Args:
        db_path: 数据库文件路径
        
    Returns:
        数据库实例
    """
    global _db
    if _db is None:
        _db = Database(db_path)
    return _db
