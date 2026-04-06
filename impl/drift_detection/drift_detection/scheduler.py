"""
漂移检测调度模块

提供定时任务接口，用于定期执行漂移检测
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from .config import AppConfig, get_config
from .monitor import DriftMonitor, get_drift_monitor

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ScheduleJob:
    """调度任务"""
    job_id: str
    name: str
    interval_seconds: int
    enabled: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    callback: Callable


@dataclass
class MonitoringTask:
    """监控任务结果"""
    task_id: str
    dimension: str
    success: bool
    failure_rate: float
    alerts_triggered: int
    executed_at: datetime
    error: Optional[str] = None


class Scheduler:
    """
    调度器
    
    管理定时任务，执行漂移检测
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        初始化调度器
        
        Args:
            config: 应用配置
        """
        self.config = config or get_config()
        self.monitor = get_drift_monitor(self.config)
        
        # 任务列表
        self._jobs: Dict[str, ScheduleJob] = {}
        
        # 任务执行历史
        self._task_history: List[MonitoringTask] = []
        
        # 最大历史记录数
        self._max_history = 100
        
        # 是否正在运行
        self._running = False
        
        logger.info("Scheduler initialized")
    
    def add_job(
        self,
        job_id: str,
        name: str,
        interval_seconds: int,
        callback: Callable,
        enabled: bool = True,
    ) -> ScheduleJob:
        """
        添加调度任务
        
        Args:
            job_id: 任务ID
            name: 任务名称
            interval_seconds: 执行间隔(秒)
            callback: 回调函数
            enabled: 是否启用
            
        Returns:
            创建的任务
        """
        job = ScheduleJob(
            job_id=job_id,
            name=name,
            interval_seconds=interval_seconds,
            enabled=enabled,
            last_run=None,
            next_run=datetime.now() + timedelta(seconds=interval_seconds),
            callback=callback,
        )
        
        self._jobs[job_id] = job
        logger.info(f"Added job: {job_id} ({name}), interval: {interval_seconds}s")
        
        return job
    
    def remove_job(self, job_id: str) -> bool:
        """
        移除任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            是否成功移除
        """
        if job_id in self._jobs:
            del self._jobs[job_id]
            logger.info(f"Removed job: {job_id}")
            return True
        return False
    
    def enable_job(self, job_id: str) -> bool:
        """
        启用任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            是否成功启用
        """
        job = self._jobs.get(job_id)
        if job:
            job.enabled = True
            job.next_run = datetime.now() + timedelta(seconds=job.interval_seconds)
            logger.info(f"Enabled job: {job_id}")
            return True
        return False
    
    def disable_job(self, job_id: str) -> bool:
        """
        禁用任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            是否成功禁用
        """
        job = self._jobs.get(job_id)
        if job:
            job.enabled = False
            job.next_run = None
            logger.info(f"Disabled job: {job_id}")
            return True
        return False
    
    def get_job(self, job_id: str) -> Optional[ScheduleJob]:
        """获取任务"""
        return self._jobs.get(job_id)
    
    def list_jobs(self) -> List[ScheduleJob]:
        """列出所有任务"""
        return list(self._jobs.values())
    
    def run_job(self, job_id: str) -> Optional[MonitoringTask]:
        """
        手动执行任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            任务执行结果
        """
        job = self._jobs.get(job_id)
        
        if not job:
            logger.error(f"Job not found: {job_id}")
            return None
        
        if not job.enabled:
            logger.warning(f"Job disabled: {job_id}")
            return None
        
        task_id = f"{job_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        executed_at = datetime.now()
        
        try:
            # 执行回调
            result = job.callback()
            
            # 更新任务状态
            job.last_run = executed_at
            job.next_run = executed_at + timedelta(seconds=job.interval_seconds)
            
            # 创建任务结果
            task = MonitoringTask(
                task_id=task_id,
                dimension=job_id,
                success=True,
                failure_rate=result.get("failure_rate", 0.0) if result else 0.0,
                alerts_triggered=result.get("alerts_triggered", 0) if result else 0,
                executed_at=executed_at,
            )
            
            self._record_task(task)
            
            logger.info(f"Job executed: {job_id}, alerts: {task.alerts_triggered}")
            return task
        
        except Exception as e:
            logger.error(f"Job execution failed: {job_id}, error: {e}")
            
            task = MonitoringTask(
                task_id=task_id,
                dimension=job_id,
                success=False,
                failure_rate=0.0,
                alerts_triggered=0,
                executed_at=executed_at,
                error=str(e),
            )
            
            self._record_task(task)
            return task
    
    def _record_task(self, task: MonitoringTask) -> None:
        """记录任务执行结果"""
        self._task_history.append(task)
        
        # 限制历史记录数量
        if len(self._task_history) > self._max_history:
            self._task_history = self._task_history[-self._max_history:]
    
    def get_task_history(
        self,
        job_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[MonitoringTask]:
        """
        获取任务执行历史
        
        Args:
            job_id: 任务ID筛选
            limit: 返回数量
            
        Returns:
            任务执行结果列表
        """
        if job_id:
            return [
                t for t in self._task_history
                if t.dimension == job_id
            ][-limit:]
        
        return self._task_history[-limit:]
    
    def start(self) -> None:
        """启动调度器"""
        self._running = True
        logger.info("Scheduler started")
    
    def stop(self) -> None:
        """停止调度器"""
        self._running = False
        logger.info("Scheduler stopped")
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    def tick(self) -> List[MonitoringTask]:
        """
        执行待处理的任务
        
        Returns:
            执行的任务结果列表
        """
        if not self._running:
            return []
        
        now = datetime.now()
        executed = []
        
        for job in self._jobs.values():
            if not job.enabled:
                continue
            
            if job.next_run and now >= job.next_run:
                result = self.run_job(job.job_id)
                if result:
                    executed.append(result)
        
        return executed


# 全局调度器实例
_scheduler: Optional[Scheduler] = None


def get_scheduler(config: Optional[AppConfig] = None) -> Scheduler:
    """
    获取调度器实例
    
    Args:
        config: 应用配置
        
    Returns:
        调度器
    """
    global _scheduler
    
    if _scheduler is None:
        _scheduler = Scheduler(config)
    
    return _scheduler


def reset_scheduler() -> Scheduler:
    """
    重置调度器
    
    Returns:
        新的调度器实例
    """
    global _scheduler
    
    _scheduler = None
    return get_scheduler()


# ==================== 便捷函数 ====================

def schedule_monitoring(
    interval_minutes: int = 60,
    dimensions: Optional[List[str]] = None,
    enabled: bool = True,
) -> ScheduleJob:
    """
    创建定时监控任务
    
    Args:
        interval_minutes: 执行间隔(分钟)
        dimensions: 要检测的维度列表，None表示所有
        enabled: 是否启用
        
    Returns:
        创建的任务
    """
    scheduler = get_scheduler()
    monitor = get_drift_monitor()
    
    def callback():
        results = monitor.detect_all()
        
        total_alerts = 0
        max_failure_rate = 0.0
        
        for dimension, detection_results in results.items():
            if dimensions and dimension not in dimensions:
                continue
            
            for result in detection_results:
                if result.is_drift:
                    total_alerts += 1
                    max_failure_rate = max(max_failure_rate, result.failure_rate)
        
        return {
            "failure_rate": max_failure_rate,
            "alerts_triggered": total_alerts,
        }
    
    job = scheduler.add_job(
        job_id="drift_monitoring",
        name="漂移检测监控",
        interval_seconds=interval_minutes * 60,
        callback=callback,
        enabled=enabled,
    )
    
    logger.info(f"Scheduled monitoring job: interval={interval_minutes}min, dimensions={dimensions}")
    
    return job


def get_drift_status() -> dict:
    """
    获取当前漂移状态API
    
    Returns:
        漂移状态字典
    """
    monitor = get_drift_monitor()
    status = monitor.get_status()
    
    return {
        "timestamp": status.timestamp.isoformat(),
        "overall_healthy": status.overall_healthy,
        "summary": status.summary,
        "dimensions": {
            dim: {
                "last_check_time": s.last_check_time.isoformat() if s.last_check_time else None,
                "last_failure_rate": s.last_failure_rate,
                "is_drift_detected": s.is_drift_detected,
                "alert_count_today": s.alert_count_today,
            }
            for dim, s in status.dimensions.items()
        },
        "recent_alerts": [
            {
                "id": a.id,
                "dimension": a.dimension.value,
                "severity": a.severity.value,
                "message": a.message,
                "failure_rate": a.failure_rate,
                "created_at": a.created_at.isoformat(),
            }
            for a in status.recent_alerts
        ],
    }


def run_monitoring_cycle() -> dict:
    """
    运行一次监控周期
    
    Returns:
        监控结果
    """
    monitor = get_drift_monitor()
    results = monitor.detect_all()
    
    total_alerts = sum(len(r) for r in results.values())
    
    return {
        "dimensions": {
            dim: {
                "drift_detected": len(results[dim]) > 0,
                "alert_count": len(results[dim]),
                "results": [
                    {
                        "is_drift": r.is_drift,
                        "failure_rate": r.failure_rate,
                        "threshold": r.threshold,
                        "severity": r.severity.value,
                        "message": r.message,
                    }
                    for r in results[dim]
                ],
            }
            for dim in results
        },
        "total_alerts": total_alerts,
        "timestamp": datetime.now().isoformat(),
    }
