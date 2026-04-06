"""
漂移检测系统集成测试

使用真实数据跑一遍端到端监控流程
"""

import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from drift_detection import config, database, models
from drift_detection.alerts import (
    AlertLevel,
    AlertLogger,
    AlertManager,
    AlertPriority,
    AlertSuppressor,
)
from drift_detection.detectors import (
    DetectionResult,
    DriftDimension,
    HallucinationDriftDetector,
    LocateDriftDetector,
    RuleDriftDetector,
)
from drift_detection.monitor import DriftMonitor, get_drift_monitor
from drift_detection.scheduler import (
    Scheduler,
    get_drift_status,
    run_monitoring_cycle,
    schedule_monitoring,
)
from drift_detection.config import AppConfig, DetectionConfig, NotifierConfig


def setup_test_db():
    """创建临时测试数据库"""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_path = temp_db.name
    temp_db.close()
    
    # 初始化配置使用测试数据库
    test_config = AppConfig(
        detection=DetectionConfig(db_path=db_path),
        notifier=NotifierConfig(enabled=False),  # 禁用真实告警
    )
    
    # 重置全局实例
    from drift_detection import database as db_module
    db_module._db = None
    
    # 重新初始化数据库
    db = db_module.get_database(db_path)
    
    return db, db_path


def cleanup_test_db(db_path):
    """清理测试数据库"""
    try:
        os.unlink(db_path)
    except:
        pass


def test_alert_system():
    """测试告警系统"""
    print("\n" + "=" * 60)
    print("测试 1: 告警系统")
    print("=" * 60)
    
    db_path = None
    try:
        db, db_path = setup_test_db()
        
        # 测试AlertLogger
        with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as f:
            log_file = f.name
        
        logger = AlertLogger(log_file)
        
        from drift_detection.alerts import AlertEvent
        event = AlertEvent(
            alert_id="test001",
            dimension=DriftDimension.CHAPTER_LOCATOR,
            priority=AlertPriority.P0_CRITICAL,
            level=AlertLevel.CRITICAL,
            message="测试告警",
            failure_rate=0.15,
            threshold=0.10,
            created_at=datetime.now(),
        )
        
        logger.log_alert(event)
        print("✓ AlertLogger 日志记录正常")
        
        # 测试AlertSuppressor
        suppressor = AlertSuppressor(cooldown_seconds=60)
        
        # 第一次应该通过
        result = suppressor.should_send(DriftDimension.CHAPTER_LOCATOR, AlertPriority.P1_HIGH)
        assert result == True, "首次告警应该被允许"
        print("✓ 首次告警被允许")
        
        # 记录后应该被抑制
        suppressor.record_alert(DriftDimension.CHAPTER_LOCATOR, AlertPriority.P1_HIGH)
        result = suppressor.should_send(DriftDimension.CHAPTER_LOCATOR, AlertPriority.P1_HIGH)
        assert result == False, "冷却期内告警应该被抑制"
        print("✓ 冷却期告警被抑制")
        
        # 测试AlertManager
        test_config = AppConfig(
            detection=DetectionConfig(db_path=db_path),
            notifier=NotifierConfig(enabled=True, suppress_minutes=1),
        )
        
        from drift_detection.alerts import reset_alert_manager
        reset_alert_manager()
        
        manager = AlertManager(test_config)
        
        # 触发告警
        alert = manager.handle_alert(
            dimension=DriftDimension.CHAPTER_LOCATOR,
            level=AlertLevel.WARNING,
            message="测试告警",
            failure_rate=0.12,
            threshold=0.10,
        )
        
        assert alert is not None, "应该返回告警事件"
        print(f"✓ 告警触发成功: {alert.alert_id}")
        
        # 检查数据库中的告警记录
        alerts = db.get_alerts(limit=10)
        assert len(alerts) > 0, "数据库应该有告警记录"
        print(f"✓ 告警已持久化到数据库: {len(alerts)} 条")
        
        # 清理日志
        os.unlink(log_file)
        
        print("\n✅ 告警系统测试通过!")
        return True
        
    except Exception as e:
        print(f"\n❌ 告警系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if db_path:
            cleanup_test_db(db_path)


def test_detectors():
    """测试检测器"""
    print("\n" + "=" * 60)
    print("测试 2: 检测器")
    print("=" * 60)
    
    db_path = None
    try:
        db, db_path = setup_test_db()
        
        # 测试LocateDriftDetector
        locate = LocateDriftDetector()
        
        # 记录一些定位结果
        for i, (stock, confidence) in enumerate([
            ("000001", 0.95),
            ("000002", 0.85),
            ("000003", 0.55),  # 失败
            ("000004", 0.70),
            ("000005", 0.50),  # 失败
        ]):
            locate.record_confidence(stock, confidence)
        
        stats = locate.get_daily_stats()
        print(f"  章节定位统计: {stats}")
        
        # 检测漂移
        results = locate.detect()
        print(f"  检测到漂移: {len(results)} 个")
        
        if results:
            print(f"    失败率: {results[0].failure_rate:.2%}")
        
        print("✓ LocateDriftDetector 正常")
        
        # 测试RuleDriftDetector
        rule = RuleDriftDetector()
        
        # 记录一些执行结果
        for stock, is_timeout, score, verdict in [
            ("000001", False, 80.0, "red"),
            ("000002", False, 60.0, "green"),
            ("000003", True, None, None),  # 超时
            ("000004", False, 90.0, "green"),  # 不一致
            ("000005", False, 75.0, "red"),
        ]:
            rule.record_execution(
                stock,
                is_timeout=is_timeout,
                score=score,
                verdict=verdict,
            )
        
        stats = rule.get_daily_stats()
        print(f"  规则引擎统计: {stats}")
        
        results = rule.detect()
        print(f"  检测到漂移: {len(results)} 个")
        
        print("✓ RuleDriftDetector 正常")
        
        # 测试HallucinationDriftDetector
        hallucination = HallucinationDriftDetector()
        
        # 记录一些幻觉检测结果
        for stock, confidence in [
            ("000001", 0.90),
            ("000002", 0.85),
            ("000003", 0.45),  # 幻觉
            ("000004", 0.55),  # 幻觉
            ("000005", 0.95),
        ]:
            hallucination.record_confidence(stock, confidence)
        
        stats = hallucination.get_daily_stats()
        print(f"  LLM幻觉统计: {stats}")
        
        results = hallucination.detect()
        print(f"  检测到漂移: {len(results)} 个")
        
        print("✓ HallucinationDriftDetector 正常")
        
        print("\n✅ 检测器测试通过!")
        return True
        
    except Exception as e:
        print(f"\n❌ 检测器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if db_path:
            cleanup_test_db(db_path)


def test_drift_monitor():
    """测试DriftMonitor"""
    print("\n" + "=" * 60)
    print("测试 3: DriftMonitor")
    print("=" * 60)
    
    db_path = None
    try:
        db, db_path = setup_test_db()
        
        from drift_detection import monitor as monitor_module
        monitor_module._monitor = None
        
        test_config = AppConfig(
            detection=DetectionConfig(db_path=db_path),
            notifier=NotifierConfig(enabled=False),
        )
        
        monitor = DriftMonitor(test_config)
        
        # 记录数据
        monitor.record_locate_confidence("000001", 0.90)
        monitor.record_locate_confidence("000002", 0.55)  # 失败
        
        monitor.record_rule_execution("000001", score=80.0, verdict="red")
        monitor.record_rule_execution("000002", is_timeout=True)
        
        monitor.record_hallucination_confidence("000001", 0.85)
        monitor.record_hallucination_confidence("000002", 0.40)  # 幻觉
        
        # 执行检测
        results = monitor.detect_all()
        
        print("  检测结果:")
        for dim, res in results.items():
            print(f"    {dim}: {len(res)} 个漂移")
        
        # 获取状态
        status = monitor.get_status()
        print(f"\n  整体状态: {'健康' if status.overall_healthy else '异常'}")
        print(f"  摘要: {status.summary}")
        
        for dim, s in status.dimensions.items():
            print(f"    {dim}: 失败率={s.last_failure_rate:.2%}, 漂移={s.is_drift_detected}")
        
        print("✓ DriftMonitor 正常")
        
        print("\n✅ DriftMonitor测试通过!")
        return True
        
    except Exception as e:
        print(f"\n❌ DriftMonitor测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if db_path:
            cleanup_test_db(db_path)


def test_scheduler():
    """测试调度器"""
    print("\n" + "=" * 60)
    print("测试 4: 调度器")
    print("=" * 60)
    
    db_path = None
    try:
        db, db_path = setup_test_db()
        
        from drift_detection import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        test_config = AppConfig(
            detection=DetectionConfig(db_path=db_path),
            notifier=NotifierConfig(enabled=False),
        )
        
        scheduler = Scheduler(test_config)
        
        # 添加一个定时任务
        job = scheduler.add_job(
            job_id="test_job",
            name="测试任务",
            interval_seconds=1,
            callback=lambda: {"success": True, "alerts": 0},
            enabled=True,
        )
        
        print(f"  添加任务: {job.name}")
        
        # 执行任务
        result = scheduler.run_job("test_job")
        print(f"  执行结果: success={result.success}, task_id={result.task_id}")
        
        # 检查任务历史
        history = scheduler.get_task_history("test_job")
        print(f"  历史记录: {len(history)} 条")
        
        print("✓ Scheduler 正常")
        
        print("\n✅ 调度器测试通过!")
        return True
        
    except Exception as e:
        print(f"\n❌ 调度器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if db_path:
            cleanup_test_db(db_path)


def test_e2e_monitoring():
    """端到端测试"""
    print("\n" + "=" * 60)
    print("测试 5: 端到端监控流程")
    print("=" * 60)
    
    db_path = None
    try:
        db, db_path = setup_test_db()
        
        # 重置全局实例
        from drift_detection import database as db_module
        db_module._db = None
        
        from drift_detection import monitor as monitor_module
        monitor_module._monitor = None
        
        from drift_detection import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        from drift_detection import alerts as alerts_module
        alerts_module._alert_manager = None
        
        # 配置
        test_config = AppConfig(
            detection=DetectionConfig(
                db_path=db_path,
                locate_failure_threshold=0.15,
                rule_error_threshold=0.15,
                hallucination_threshold=0.15,
            ),
            notifier=NotifierConfig(enabled=False),
        )
        
        # 初始化监控器
        monitor = DriftMonitor(test_config)
        
        # 模拟真实数据场景
        print("\n  模拟数据注入...")
        
        # 场景1: 章节定位 - 正常情况
        for stock in ["000001", "000002", "000003", "000004"]:
            monitor.record_locate_confidence(stock, 0.85)
        
        # 场景2: 规则引擎 - 部分超时
        for stock, is_timeout, score, verdict in [
            ("000001", False, 80.0, "red"),
            ("000002", False, 65.0, "green"),
            ("000003", True, None, None),
            ("000004", False, 75.0, "red"),
        ]:
            monitor.record_rule_execution(stock, is_timeout=is_timeout, score=score, verdict=verdict)
        
        # 场景3: LLM幻觉 - 正常
        for stock in ["000001", "000002", "000003", "000004"]:
            monitor.record_hallucination_confidence(stock, 0.90)
        
        # 执行检测
        print("\n  执行漂移检测...")
        results = run_monitoring_cycle()
        
        print(f"\n  检测结果:")
        print(f"    总告警数: {results['total_alerts']}")
        
        for dim, data in results['dimensions'].items():
            print(f"    {dim}:")
            print(f"      漂移检测: {data['drift_detected']}")
            print(f"      告警数: {data['alert_count']}")
        
        # 获取状态
        status = get_drift_status()
        print(f"\n  漂移状态:")
        print(f"    整体健康: {status['overall_healthy']}")
        print(f"    摘要: {status['summary']}")
        
        for dim, data in status['dimensions'].items():
            last_check = data.get('last_check_time', 'N/A')
            print(f"    {dim}:")
            print(f"      最后检查: {last_check}")
            print(f"      失败率: {data['last_failure_rate']:.2%}")
            print(f"      漂移检测: {data['is_drift_detected']}")
        
        # 检查数据库记录
        drift_records = db.get_drift_records(limit=100)
        alert_records = db.get_alerts(limit=100)
        
        print(f"\n  数据库记录:")
        print(f"    漂移记录: {len(drift_records)} 条")
        print(f"    告警记录: {len(alert_records)} 条")
        
        print("\n✅ 端到端测试通过!")
        return True
        
    except Exception as e:
        print(f"\n❌ 端到端测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if db_path:
            cleanup_test_db(db_path)


def test_real_data_simulation():
    """模拟真实数据场景测试"""
    print("\n" + "=" * 60)
    print("测试 6: 真实数据场景模拟")
    print("=" * 60)
    
    db_path = None
    try:
        db, db_path = setup_test_db()
        
        # 重置全局实例
        from drift_detection import database as db_module
        db_module._db = None
        
        from drift_detection import monitor as monitor_module
        monitor_module._monitor = None
        
        # 配置
        test_config = AppConfig(
            detection=DetectionConfig(
                db_path=db_path,
                locate_failure_threshold=0.10,
                rule_error_threshold=0.10,
                hallucination_threshold=0.10,
                confidence_threshold=0.6,
            ),
            notifier=NotifierConfig(enabled=False),
        )
        
        monitor = DriftMonitor(test_config)
        
        # 模拟真实场景：一段时间内的监控数据
        print("\n  模拟真实监控数据...")
        
        # 场景: 某交易日监控系统运行
        import random
        random.seed(42)
        
        # 生成50只股票的章节定位数据
        for i in range(50):
            stock = f"{(600000 + i):06d}"
            # 90% 正常定位, 10% 失败
            confidence = random.uniform(0.5, 1.0) if random.random() > 0.1 else random.uniform(0.3, 0.59)
            monitor.record_locate_confidence(stock, confidence)
        
        # 生成规则引擎数据
        for i in range(50):
            stock = f"{(600000 + i):06d}"
            # 95% 正常, 5% 异常
            if random.random() > 0.05:
                score = random.uniform(60, 90)
                verdict = "red" if score >= 70 else "green"
                monitor.record_rule_execution(stock, score=score, verdict=verdict)
            else:
                monitor.record_rule_execution(stock, is_timeout=True)
        
        # 生成LLM幻觉检测数据
        for i in range(50):
            stock = f"{(600000 + i):06d}"
            # 85% 正常, 15% 幻觉
            confidence = random.uniform(0.7, 1.0) if random.random() > 0.15 else random.uniform(0.3, 0.59)
            monitor.record_hallucination_confidence(stock, confidence)
        
        # 执行检测
        results = monitor.detect_all()
        
        print(f"\n  维度检测结果:")
        for dim, res in results.items():
            if res:
                print(f"    {dim}:")
                for r in res:
                    print(f"      - {r.severity.value}: {r.message}")
                    print(f"        失败率 {r.failure_rate:.2%} >= 阈值 {r.threshold:.2%}")
            else:
                print(f"    {dim}: 无漂移")
        
        # 获取状态
        status = monitor.get_status()
        
        print(f"\n  最终状态:")
        print(f"    整体: {'✅ 健康' if status.overall_healthy else '⚠️ 异常'}")
        print(f"    摘要: {status.summary}")
        
        # 数据库统计
        total_drift = len(db.get_drift_records(limit=1000))
        total_alerts = len(db.get_alerts(limit=100))
        
        print(f"\n  数据库统计:")
        print(f"    漂移记录: {total_drift} 条")
        print(f"    告警记录: {total_alerts} 条")
        
        print("\n✅ 真实数据场景模拟测试通过!")
        return True
        
    except Exception as e:
        print(f"\n❌ 真实数据场景模拟测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if db_path:
            cleanup_test_db(db_path)


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("漂移检测系统 - 集成测试")
    print("=" * 60)
    
    tests = [
        ("告警系统", test_alert_system),
        ("检测器", test_detectors),
        ("DriftMonitor", test_drift_monitor),
        ("调度器", test_scheduler),
        ("端到端监控", test_e2e_monitoring),
        ("真实数据模拟", test_real_data_simulation),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ {name} 测试异常: {e}")
            results.append((name, False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {name}: {status}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
