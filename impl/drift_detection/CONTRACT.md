# 漂移检测系统实施合同

**项目**: A股深度分析系统 - 漂移检测模块  
**版本**: v1.0  
**日期**: 2026-04-06  
**角色**: 架构师（实施Agent）

---

## 1. 任务范围

### 1.1 背景

系统已完成P0+P1+P2模块8（投资结论模块），现需构建**漂移检测系统**，实时监控模型/管道性能退化。

### 1.2 监控维度

| 维度 | 描述 | 指标 |
|------|------|------|
| **章节定位失败率** | MD&A章节定位精度 | 置信度 < 0.6 视为失败 |
| **规则引擎质量** | 红旗引擎评分一致性 | score异常/超时率 |
| **LLM幻觉率** | LLM分析结果可信度 | 幻觉检测/一致性校验 |

### 1.3 交付物

1. 漂移检测服务（独立微服务）
2. 监控面板（Web UI）
3. 告警通知（Webhook/邮件）
4. 历史数据存储（SQLite/时序库）
5. API接口（RESTful）

---

## 2. 验收标准

### 2.1 功能验收

| # | 验收项 | 标准 |
|---|--------|------|
| F1 | 章节定位监控 | 每日汇总定位失败率，置信度<0.6计入失败 |
| F2 | 规则引擎监控 | 记录红旗引擎超时/异常，统计错误率 |
| F3 | LLM幻觉检测 | 实现一致性校验，检测逻辑矛盾 |
| F4 | 告警触发 | 失败率超过阈值(默认10%)自动告警 |
| F5 | 数据持久化 | 监控数据保留≥90天 |
| F6 | API查询 | 支持按股票/时间范围查询漂移历史 |

### 2.2 性能验收

| # | 指标 | 目标 |
|---|------|------|
| P1 | 监控延迟 | 单次检测 < 5秒 |
| P2 | 并发能力 | 支持 ≥ 100股票/天并发检测 |
| P3 | 可用性 | 服务可用率 ≥ 99.5% |

### 2.3 质量验收

| # | 标准 |
|---|------|
| Q1 | 单元测试覆盖率 ≥ 70% |
| Q2 | 关键路径有日志记录 |
| Q3 | 配置文件外部化 |

---

## 3. 技术方案

### 3.1 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                     漂移检测系统架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ 章节定位监控  │    │ 规则引擎监控  │    │ LLM幻觉检测  │       │
│  │   Module     │    │   Module     │    │   Module     │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│         │                   │                   │                │
│         └───────────────────┼───────────────────┘                │
│                             ▼                                    │
│                    ┌──────────────┐                             │
│                    │  聚合分析器    │                             │
│                    │  Aggregator  │                             │
│                    └──────┬───────┘                             │
│                           ▼                                      │
│  ┌────────────────────────────────────────────────────────┐     │
│  │                    决策引擎                              │     │
│  │  • 阈值比较  • 趋势分析  • 告警判断                      │     │
│  └──────────────────────┬───────────────────────────────┘     │
│                         ▼                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  告警通知   │  │  存储层     │  │   API层    │             │
│  │ Notifier   │  │  SQLite    │  │  FastAPI   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心模块

#### 3.2.1 章节定位监控 (ChapterLocatorMonitor)

```python
class ChapterLocatorMonitor:
    """监控MD&A章节定位成功率"""
    
    # 阈值配置
    CONFIDENCE_THRESHOLD = 0.6
    FAILURE_RATE_THRESHOLD = 0.10  # 10% 告警阈值
    
    def record(self, stock_code: str, confidence: float) -> DriftRecord:
        """记录单次定位结果"""
        
    def aggregate_daily(self) -> DailyStats:
        """聚合每日失败率"""
        
    def check_drift(self) -> List[Alert]:
        """检测漂移并触发告警"""
```

#### 3.2.2 规则引擎监控 (RedFlagEngineMonitor)

```python
class RedFlagEngineMonitor:
    """监控红旗引擎质量"""
    
    # 监控指标
    TIMEOUT_THRESHOLD = 180  # 秒
    SCORE_ANOMALY_RANGE = (0, 100)  # 合法范围
    
    def record(self, stock_code: str, result: EngineResult) -> DriftRecord:
        """记录引擎执行结果"""
        
    def detect_timeout(self) -> List[DriftRecord]:
        """检测超时事件"""
        
    def detect_inconsistency(self) -> List[DriftRecord]:
        """检测score/verdict逻辑不一致"""
```

#### 3.2.3 LLM幻觉检测 (LLMHallucinationDetector)

```python
class LLMHallucinationDetector:
    """检测LLM分析结果幻觉"""
    
    def detect_contradiction(self, analysis_result: dict) -> bool:
        """检测逻辑矛盾"""
        
    def cross_validate(self, llm_result: str, facts: list) -> float:
        """交叉验证一致性"""
        
    def record_confidence(self, stock_code: str, score: float) -> DriftRecord:
        """记录置信度评分"""
```

### 3.3 技术栈

| 组件 | 技术选型 | 理由 |
|------|----------|------|
| API框架 | FastAPI | 高性能异步支持 |
| 存储 | SQLite | 轻量易部署 |
| 调度 | APScheduler | 支持定时任务 |
| 告警 | Webhook | 灵活集成 |
| 监控面板 | Streamlit | 快速开发原型 |

### 3.4 数据模型

```python
class DriftRecord:
    stock_code: str
    dimension: str  # chapter_locator | redflag_engine | llm_hallucination
    metric: str
    value: float
    timestamp: datetime
    metadata: dict

class Alert:
    alert_id: str
    dimension: str
    failure_rate: float
    threshold: float
    severity: str  # info | warning | critical
    created_at: datetime
```

---

## 4. 时间估算

### 4.1 阶段划分

| 阶段 | 任务 | 工期 | 累计 |
|------|------|------|------|
| **Phase 1** | 基础设施搭建 | 1天 | 1天 |
| **Phase 2** | 章节定位监控 | 2天 | 3天 |
| **Phase 3** | 规则引擎监控 | 2天 | 5天 |
| **Phase 4** | LLM幻觉检测 | 2天 | 7天 |
| **Phase 5** | 告警通知 | 1天 | 8天 |
| **Phase 6** | API与面板 | 2天 | 10天 |
| **Phase 7** | 联调测试 | 2天 | 12天 |

### 4.2 资源投入

| 角色 | 工时 |
|------|------|
| 后端开发 | 10人日 |
| 测试 | 2人日 |
| **总计** | **12人日** |

---

## 5. 实施步骤

### Step 1: 基础设施搭建

```
[ ] 创建项目目录结构
    drift_detection/
    ├── api/           # API层
    ├── monitor/       # 监控模块
    ├── detector/      # 检测器
    ├── storage/       # 存储层
    ├── notifier/      # 告警
    └── web/           # Web面板

[ ] 初始化Python环境
[ ] 配置日志系统
[ ] 创建数据库Schema
```

### Step 2: 章节定位监控实现

```
[ ] 实现ChapterLocatorMonitor类
[ ] 配置置信度阈值(CONFIDENCE_THRESHOLD=0.6)
[ ] 实现每日聚合统计
[ ] 编写单元测试
[ ] 对接现有章节定位模块的日志输出
```

### Step 3: 规则引擎监控实现

```
[ ] 实现RedFlagEngineMonitor类
[ ] 实现超时检测逻辑
[ ] 实现score/verdict一致性校验
[ ] 编写单元测试
[ ] 对接红旗引擎执行日志
```

### Step 4: LLM幻觉检测实现

```
[ ] 实现LLMHallucinationDetector类
[ ] 实现逻辑矛盾检测算法
[ ] 实现交叉验证逻辑
[ ] 编写单元测试
```

### Step 5: 告警通知实现

```
[ ] 实现Notifier基类
[ ] 实现Webhook告警
[ ] 配置告警阈值
[ ] 实现告警抑制(避免风暴)
```

### Step 6: API与Web面板

```
[ ] 实现RESTful API
    - GET /drift/{dimension}
    - GET /drift/history
    - POST /drift/config
    
[ ] 实现Streamlit监控面板
    - 漂移趋势图
    - 实时告警列表
    - 配置管理
```

### Step 7: 联调测试

```
[ ] 与现有系统集成测试
[ ] 端到端测试
[ ] 性能压测
[ ] 上线部署
```

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 现有日志格式变化 | 监控数据采集失败 | 设计容错解析，支持多格式 |
| LLM API不可用 | 幻觉检测暂停 | 记录降级状态，保留检测能力 |
| 阈值难以确定 | 告警误报 | 上线后基于实际数据调优 |

---

## 7. 后续迭代

| 优先级 | 特性 |
|--------|------|
| P1 | 时序数据库迁移(InfluxDB) |
| P1 | 多维度关联分析 |
| P2 | 自动阈值学习 |
| P2 | 根因分析推荐 |

---

**签署**:

- [ ] 架构师: _____________ 日期: _______
- [ ] 产品负责人: _____________ 日期: _______
