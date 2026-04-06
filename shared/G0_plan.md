# G0Gate 实施计划：整体架构设计

> 版本：v1.0
> 日期：2026-04-03
> 制定：实施Agent（Architect）
> 待审查：评估Agent（Critic）

---

## 一、整体目录结构设计

```
/home/ponder/.openclaw/workspace/astock-implementation/
├── shared/                          # 跨模块共享资源
│   ├── G0_plan.md                   # 本文档（架构确认）
│   ├── data_schema.md               # 统一数据Schema定义
│   └── dependencies.md              # 模块依赖关系说明
│
├── impl/                            # 实施代码主目录
│   ├── module9_governance/          # P0-模块9：治理筛查
│   │   ├── __init__.py
│   │   ├── screen.py                # 治理筛查主入口
│   │   ├── equity_pledge.py         # 股权质押追踪
│   │   ├── audit_history.py         # 审计历史数据库
│   │   ├── shareholder_structure.py  # 股权结构穿透
│   │   └── goodwill_monitor.py       # 商誉/并购监控
│   │
│   ├── module2_financial/           # P0-历史财务数据管道
│   │   ├── __init__.py
│   │   ├── data_fetcher.py          # akshare数据拉取
│   │   ├── hdf5_storage.py          # HDF5存储管理
│   │   ├── roic_calculator.py       # ROIC计算引擎
│   │   ├── dupont_analyzer.py       # 杜邦分解
│   │   └── cashflow_analyzer.py     # 现金流分析
│   │
│   ├── industry_thresholds/          # P0-行业阈值数据库
│   │   ├── __init__.py
│   │   ├── db_schema.sql            # PostgreSQL Schema
│   │   ├── threshold_api.py         # 阈值API（get_threshold/get_red_flags）
│   │   ├── percentile_engine.py     # 分位数计算引擎
│   │   ├── sw_classifier.py         # 申万行业分类
│   │   └── combo_flags.py           # 三大危险信号组合
│   │
│   ├── module6_mda/                 # P0-模块6：MD&A PDF解析管道
│   │   ├── __init__.py
│   │   ├── pdf_downloader.py        # PDF下载（5级降级）
│   │   ├── text_extractor.py        # 文字提取（PyMuPDF/pdfplumber/PaddleOCR）
│   │   ├── chapter_locator.py       # 章节定位（4级降级）
│   │   ├── rule_splitter.py         # 规则引擎切分
│   │   ├── llm_analyzer.py          # LLM深度分析（约束性Prompt）
│   │   ├── quality_scorer.py        # 质量评分系统
│   │   └── promise_tracker.py       # 承诺-兑现对照
│   │
│   ├── module7_announcements/        # P0-模块7：公告数据管道
│   │   ├── __init__.py
│   │   ├── equity_change_collector.py   # 股权变动采集
│   │   ├── inquiry_letter_collector.py  # 问询函采集
│   │   ├── ir_records_collector.py      # 投资者关系记录
│   │   ├── ma_collector.py               # 并购重组采集
│   │   └── severity_classifier.py        # 问询函严重程度分级
│   │
│   ├── module3_red_flags/           # P1-盈利质量红旗引擎
│   │   ├── __init__.py
│   │   ├── cash_quality.py         # 现金流质量检测
│   │   ├── monetary_validation.py   # 货币资金真实性验证
│   │   └── inquiry_db.py            # 监管问询函数据库检索
│   │
│   ├── module4_asset_quality/       # P1-资产质量红旗引擎
│   │   ├── __init__.py
│   │   ├── ar_quality.py           # 应收账款质量
│   │   ├── inventory_quality.py    # 存货质量
│   │   ├── construction_wip.py      # 在建工程检测
│   │   └── goodwill.py              # 商誉检测
│   │
│   ├── module5_valuation/           # P1-估值分析引擎
│   │   ├── __init__.py
│   │   ├── industry_matrix.py       # 行业差异化估值矩阵
│   │   ├── graham_number.py        # 格雷厄姆数（清零测试）
│   │   ├── dcf_model.py            # DCF简化版+敏感性分析
│   │   ├── relative_valuation.py    # 相对估值（PE/PB/PS分位）
│   │   ├── book_value_floor.py     # 清算价值底线
│   │   └── trap_detector.py        # 价值陷阱概率评估
│   │
│   ├── module8_conclusion/         # P2-投资结论引擎
│   │   ├── __init__.py
│   │   ├── rating_engine.py        # 综合评级引擎（5档）
│   │   ├── red_flag_aggregator.py  # 红旗清单汇总（4层权重）
│   │   ├── reverse_trigger.py      # 逆向操作触发器
│   │   └── operation_matrix.py     # 投资操作矩阵
│   │
│   ├── charts/                      # P1-图表自动化
│   │   ├── __init__.py
│   │   ├── roic_wacc_trend.py      # 图表1
│   │   ├── revenue_profit.py       # 图表2
│   │   ├── dupont_factors.py       # 图表3+4
│   │   ├── cashflow_trend.py       # 图表5+6
│   │   ├── asset_trend.py          # 图表7
│   │   ├── turnover_days.py        # 图表8
│   │   ├── leverage_ratio.py       # 图表9
│   │   ├── dividend_eps.py         # 图表10+11
│   │   ├── shareholder_price.py    # 图表12
│   │   ├── ma_timeline.py         # 图表13
│   │   ├── pe_pb_percentile.py    # 图表14
│   │   └── dcf_heatmap.py         # 图表15
│   │
│   ├── quality_control/            # P1-质量控制系统
│   │   ├── __init__.py
│   │   ├── schema_checker.py      # 第一线：Schema校验
│   │   ├── stats_monitor.py       # 第二线：统计监控+分层抽样
│   │   └── incident_tracker.py     # 第三线：Incident Report闭环
│   │
│   ├── report_generator/           # P2-报告生成引擎
│   │   ├── __init__.py
│   │   ├── report_builder.py       # 报告组装主逻辑
│   │   ├── module0_conclusion.py  # 模块0：一分钟结论页
│   │   ├── module1_business.py    # 模块1：商业模式
│   │   └── appendix.py            # 附录汇总表
│   │
│   └── utils/                      # 通用工具
│       ├── __init__.py
│       ├── logger.py               # 统一日志（结构化JSON日志）
│       ├── cache.py                # 版本化缓存管理
│       ├── drift_detector.py       # 漂移检测（P2）
│       └── config.py               # 全局配置管理
│
├── tests/                          # 测试目录
│   ├── test_module9.py             # 治理筛查测试（永新+问题公司各1家）
│   ├── test_industry_thresholds.py # 阈值数据库测试
│   ├── test_mda_pipeline.py        # MD&A管道端到端测试
│   └── test_red_flags.py          # 红旗引擎测试（康美/康得新）
│
├── data/                           # 数据存储（gitignore）
│   ├── hdf5/                      # HDF5财务数据库
│   ├── postgres/                   # PostgreSQL数据文件
│   └── cache/                     # 版本化缓存
│
├── config/                         # 配置文件
│   ├── data_sources.yaml           # 数据源配置
│   ├── industry_config.yaml        # 申万行业分类配置
│   ├── llm_prompts.yaml           # LLM Prompt模板
│   └── quality_thresholds.yaml     # 质量阈值配置
│
├── scripts/                        # 运维脚本
│   ├── setup_postgres.sh           # PostgreSQL初始化
│   ├── setup_hdf5.sh              # HDF5初始化
│   └── run_pipeline.sh             # 端到端测试脚本
│
├── requirements.txt                # Python依赖
└── README.md                       # 项目说明
```

---

## 二、模块间依赖关系图

```
┌─────────────────────────────────────────────────────────┐
│                  数据基础设施层（无依赖）                 │
│   HDF5财务数据库  ←  module2_financial 写入            │
│   PostgreSQL阈值库 ←  industry_thresholds 写入          │
│   公告数据库      ←  module7_announcements 写入         │
└────────────────────────────┬────────────────────────────┘
                             │ 数据供给
                             ▼
┌─────────────────────────────────────────────────────────┐
│  P0阶段（可并行实施）                                    │
│                                                          │
│  module9_governance ──→ 治理筛查结论（通过/存疑/高风险）  │
│       │                                                 │
│       └───→ 阻断机制：治理高风险 → 报告终止，不进后续模块│
│                                                          │
│  module2_financial ──→ HDF5存储 ──→ 供给所有下游模块      │
│  industry_thresholds ──→ PostgreSQL ──→ 供给模块3/4/5    │
│  module7_announcements ──→ 公告数据库 ──→ 供给模块8       │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│  P1阶段（依赖P0完成）                                    │
│                                                          │
│  module3_red_flags ──→ 依赖：module2 + industry_thresholds│
│  module4_asset_quality ──→ 依赖：module2 + thresholds    │
│  module5_valuation ──→ 依赖：module2 + module3 + module4 │
│  charts ──→ 依赖：module2 + module5 + module7            │
│  module6_mda ──→ 独立管道，LLM分析                       │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│  P2阶段（依赖P1核心模块）                                │
│                                                          │
│  module8_conclusion ──→ 依赖：module1-7 全部完成         │
│  report_generator ──→ 依赖：所有模块                    │
│  quality_control ──→ 跨阶段质量监控                      │
│  drift_detector ──→ P2持续监控                          │
└─────────────────────────────────────────────────────────┘
```

---

## 三、数据流向设计

### 3.1 财务数据流

```
akshare API
    ↓
data_fetcher.py（异常重试+降级）
    ↓
HDF5存储（版本化管理）
    ↓
roic_calculator.py → dupont_analyzer.py → cashflow_analyzer.py
    ↓
module3_red_flags / module4_asset_quality / module5_valuation
```

### 3.2 MD&A数据流

```
年报PDF URL
    ↓
pdf_downloader.py（brotli降级）
    ↓
text_extractor.py（PyMuPDF → pdfplumber → PaddleOCR → Tesseract）
    ↓
chapter_locator.py（TOC → 层级推断 → 关键词扫描 → 字体特征）
    ↓
rule_splitter.py（规则引擎切分4个子节）
    ↓
llm_analyzer.py（仅战略子节，约束性Prompt）
    ↓
quality_scorer.py（质量评分）
    ↓
promise_tracker.py（承诺-兑现对照）
```

### 3.3 公告数据流

```
东方财富API ──┐
              ├──→ equity_change_collector.py（去重+合并）
巨潮API ─────┘
              ↓
severity_classifier.py（4级分类）
              ↓
公告数据库（PostgreSQL JSONB）
              ↓
module8_conclusion（投资结论）
```

---

## 四、关键技术选型

### 4.1 语言与运行时

| 层级 | 选择 | 备选方案 | 选型理由 |
|------|------|---------|---------|
| **主力语言** | Python 3.11+ | — | 数据科学生态最完整，PDF/LLM集成最佳 |
| **LLM调用** | OpenAI API (gpt-4o-mini) | Claude API / 国产模型 | Prompt约束成熟，幻觉控制方案完善 |
| **结构化数据存储** | PostgreSQL 15+ (JSONB) | SQLite (dev) | 阈值历史快照+公告JSONB查询最优 |
| **财务时间序列存储** | HDF5 (h5py) | Parquet | 已有26k条记录，HDF5兼容性好 |
| **PDF处理** | PyMuPDF + pdfplumber | Pyppeteer (JS渲染) | 速度最快，降级链完整 |
| **OCR** | PaddleOCR | Tesseract | 中文优化，PaddleOCR速度快 |
| **图表生成** | matplotlib + seaborn | Plotly (交互) | 批量静态图，渲染稳定 |
| **HTTP请求** | httpx + tenacity | requests | 异步+自动重试，连接复用 |
| **配置管理** | YAML | TOML | 可读性好，支持注释 |

### 4.2 数据库选型详细说明

```
PostgreSQL（行业阈值库 + 公告数据库）
├── 优势：JSONB原生支持，历史快照查询效率高
├── 备选1：MySQL（如果部署环境限制）→ 降级为JSON存储
└── 备选2：SQLite（仅dev环境）→ 不适用于生产

HDF5（财务数据库）
├── 优势：列压缩率高，Python生态完善，已有数据可复用
├── 备选1：Parquet（如果未来迁移到Spark）→ 预留迁移路径
└── 注意：HDF5不是数据库，需上层封装版本化管理逻辑
```

### 4.3 LLM集成方案

```
约束性Prompt三层保障：
├── 第一层：Prompt约束（数字必须原文引用，禁止模糊词）
├── 第二层：Schema校验（结构化输出，类型检查）
└── 第三层：后处理验证（数字一致性交叉检查）

降级策略：
├── gpt-4o-mini → gpt-4o（质量优先）
├── OpenAI → Claude（如果API不可用）
└── LLM失败 → 规则引擎兜底（仅提取确定性字段）
```

---

## 五、当前阶段（P0）具体任务分解

### 第一周：模块9优先（治理筛查）

```
任务清单：
[ ] 企查查/天眼查API接入（或手工数据接口）
[ ] 股权结构穿透分析模块（screen.py）
[ ] 股权质押比例追踪（equity_pledge.py）
[ ] 审计意见历史数据库（audit_history.py，5年）
[ ] 商誉/总资产监控（goodwill_monitor.py）
[ ] 治理综合判断逻辑（通过/存疑/高风险）

验收标准：
对002014永新股份 + 1家问题公司（如康美药业）
5分钟内输出治理筛查结论

输出：module9_governance/screen.py
```

### 第2-3周：历史财务数据管道

```
任务清单：
[ ] akshare全量数据拉取封装（异常重试+降级）
[ ] HDF5存储管理器（版本化管理，支持增量更新）
[ ] ROIC计算引擎（两种方法：简易法+详细法）
[ ] 杜邦三因子分解
[ ] 现金流轨迹分析（经营CF/投资CF/筹资CF）
[ ] 模块2对外API设计（供其他模块调用）

数据依赖：HDF5已有26k条记录
输出：module2_financial/ + data/hdf5/
```

### 第2-4周：行业阈值数据库

```
任务清单：
[ ] PostgreSQL搭建 + Schema初始化（db_schema.sql）
[ ] 申万三级行业分类表（150-170个行业）
[ ] akshare全量数据 → HDF5 → PostgreSQL管道
[ ] 分位数计算引擎（percentile_engine.py）
[ ] 阈值API封装（get_threshold / get_red_flags）
[ ] 三大危险信号组合逻辑（combo_flags.py）
[ ] Fallback机制（数据不足时降级逻辑）

验收标准：
分位数计算正确性测试（已知数据验证）
Fallback触发条件测试

输出：industry_thresholds/ + data/postgres/
```

### 第3-5周：MD&A PDF解析管道

```
任务清单：
[ ] PDF下载器（5级降级：标准→brotli→pdfplumber→PaddleOCR→Tesseract）
[ ] 文字提取器（extractor降级链）
[ ] 章节定位器（4级降级：TOC书签→层级推断→关键词→字体特征）
[ ] 规则引擎切分（4个子节映射）
[ ] LLM分析器（约束性Prompt + 3层幻觉保障）
[ ] 质量评分系统（quality_scorer.py）
[ ] 承诺兑现对照（promise_tracker.py）

验收标准：
对002014永新股份近5年年报
端到端成功率 ≥ 70%
章节定位覆盖率 ≥ 98%

输出：module6_mda/
```

### 第4-6周：公告数据管道

```
任务清单：
[ ] 东方财富API接入（股权变动）
[ ] 巨潮API接入（问询函/并购重组）
[ ] 数据去重+合并逻辑
[ ] 问询函4级严重程度分类器
[ ] 股权质押比例变化追踪
[ ] 数据完整性标注（注明统计缺口）

验收标准：
股权变动覆盖率 ≥ 90-93%
问询函覆盖率 ≥ 97-98%

输出：module7_announcements/ + data/postgres/announcements.db
```

---

## 六、G0Gate审查清单（自检）

### 架构层面
- [ ] 数据依赖关系无循环引用：module9 → 阻断后续，module2 → 全模块共享
- [ ] 错误处理完整：每个管道节点有降级策略（PDF 5级，API 3级重试）
- [ ] 可观测性：结构化JSON日志（模块名+股票代码+耗时+状态码）

### 技术选型合理性
- [ ] Python主力语言：数据科学生态最优
- [ ] PostgreSQL：JSONB + 历史快照查询最优
- [ ] HDF5：已有数据兼容，列压缩率高
- [ ] LLM三层幻觉保障：Prompt + Schema + 后处理

### 实施计划完整性
- [ ] P0阶段6大任务全部覆盖（模块9/2/阈值库/MD&A/公告/图表准备）
- [ ] 每个Gate有明确验收标准
- [ ] 备选技术方案覆盖主要风险点

### 质量控制设计
- [ ] 三线防线：Schema校验 → 统计监控 → Incident Report
- [ ] 漂移检测：章节定位失败率 / 规则引擎质量
- [ ] 无前视偏差设计：数据版本化管理

### 性能约束
- [ ] 单只股票完整分析 < 3小时（设计评估：PDF解析最大瓶颈）
- [ ] 内存峰值 < 4GB（HDF5分块读取策略）
- [ ] 增量处理 < 2小时（版本化缓存设计）

---

## 七、待评估Agent审查的决策点

### 决策点1：PostgreSQL vs MySQL
- 当前选型：PostgreSQL（JSONB原生支持，历史快照查询优）
- 备选：MySQL（如果部署环境限制）
- **请评估Agent判断**：是否有部署环境约束？

### 决策点2：HDF5 vs Parquet
- 当前选型：HDF5（已有数据可复用，列压缩率高）
- 备选：Parquet（未来Spark兼容性好）
- **请评估Agent判断**：是否需要预留Spark迁移路径？

### 决策点3：模块9优先级是否合理
- 当前计划：模块9（治理）第一周优先，因为它是阻断性检查
- 备选：先做模块2（财务管道），治理筛查放在有了数据之后
- **请评估Agent判断**：治理筛查是否必须先于财务管道？

### 决策点4：LLM选型
- 当前选型：OpenAI gpt-4o-mini（成本+速度平衡）
- 备选1：Claude API（如果OpenAI不可用）
- 备选2：国产模型（如果数据合规要求）
- **请评估Agent判断**：是否有合规/可用性约束？

---

## 八、3个中度问题的解决方案

> 本节为评估Agent审查意见的正式回应，详细方案见 `G0_issue_resolutions.md`

### 问题1解决：PostgreSQL→MySQL降级方案

**推荐方案**：方案A（MySQL 8.0 虚拟列 + 表达式索引）

**具体措施**：
- 在 `industry_thresholds/db_schema.sql` 中同时提供两套Schema（PostgreSQL JSONB主方案 + MySQL虚拟列降级方案）
- JSONB历史快照字段（`p10_value`, `p50_value`, `p90_value`）降级为MySQL `GENERATED ALWAYS ... STORED` 虚拟列
- 在虚拟列上建B-tree复合索引，替代PostgreSQL GIN索引
- 公告JSONB标签查询降级为 `JSON_CONTAINS()` 函数

**API重写清单**（预计2-3人日）：
- `get_threshold()` → 改用虚拟列 `p50_value` 索引查询
- `get_red_flags()` → `JSON_CONTAINS()` 替代 `@>` 操作符
- `query_announcements()` → 标签数组查询改写
- 业务逻辑不变，仅数据访问层调整

**接口抽象层**：
- 新增 `db/base.py`（抽象基类 `ThresholdDBAdapter`）
- 新增 `db/postgres.py`（主方案实现）
- 新增 `db/mysql.py`（降级方案实现）
- 新增 `db/factory.py`（`get_adapter()` 工厂函数）
- `threshold_api.py` 改用 `get_adapter()` 获取数据库实例

**验收标准**：同一套API在PostgreSQL和MySQL下返回完全一致的结果

---

### 问题2解决：LLM合规性预评估 + 中文能力实测

**推荐方案**：方案A优先实测（1-2天）+ Claude API备用

**实施路径**：

```
第1周（第1-2天）P0合规预评估（与模块9实施并行）：
├── Step 1：gpt-4o-mini中文年报提取准确率实测
│   ├── 测试集：永新002014 2024年报（5页战略子节人工标注，约500字段）
│   ├── 达标标准：准确率 ≥ 85% → 保留gpt-4o-mini
│   ├── 70-85% → 加few-shot再测一轮
│   └── < 70% → 切换Claude或DeepSeek
├── Step 2：数据出境合规评估（对照《数据安全法》重要数据定义）
└── 结论分支：
    ├── 无合规强制 + 准确率达标 → 保留 gpt-4o-mini
    └── 有合规强制 OR 准确率不达标 → 2-3天内接入Claude API
```

**Claude API备用接入**（已封装，切换成本低）：
- `module6_mda/llm_analyzer.py` 已有抽象设计
- 只需新增 `claude_client.py`，复用现有三层幻觉保障Prompt
- Prompt重校准：1-2人日（中文财务术语few-shot examples）

**国产模型备选**（DeepSeek V3）：
- API价格与gpt-4o-mini相近（$0.14/1M tokens）
- 中文财报能力中等偏上，但幻觉率需重新评估
- 接入方式与Claude类似（OpenAI兼容接口）

**补充到实施计划（第1周）**：
```
P0合规预评估（1-2人日，并行执行，不阻塞模块9）：
[ ] 年报数据出境合规评估（对照《数据安全法》重要数据定义）
[ ] gpt-4o-mini中文年报提取准确率实测（永新2024年报标注集）
[ ] 达标则保留；不达标则2-3天内启动Claude API接入
[ ] Prompt模板在备用模型上重校准（1-2人日）
```

---

### 问题3解决：治理模块数据源方案

**推荐方案**：混合数据源（免费优先，企查查作补充）

**数据源优先级**：

```
第一层（免费，优先使用）：
├── 股权结构：akshare.StockShareholderResearch + 年报附注
├── 审计意见：巨潮API（cninfo.com.cn）或 akshare.AuditNote
└── 股权质押比例：akshare.StockInfoPledge

第二层（企查查付费API，补充缺口）：
└── 仅当免费数据覆盖率 < 80% 时启用
    ¥2000-3000/月（基础版），成本可控
    季度更新一次，不需实时接入

第三层（手工）：仅用于系统验证阶段（3-5家公司）
```

**最小可验证数据集**（3项核心数据，第1周验收）：

| 数据项 | 来源 | 覆盖率目标 | 更新频率 |
|--------|------|-----------|---------|
| 股权结构（前5大股东+持股比例） | 年报 + akshare | ≥ 90% | 年度 |
| 审计意见（近5年） | 巨潮API | 100% | 年度 |
| 股权质押比例（总质押/总股本） | akshare + 年报附注 | ≥ 80% | 季度 |

**实施计划补充（第1周Day 1-4）**：
```
Day 1-2：免费数据源接入
[ ] akshare.StockShareholderResearch - 股权结构
[ ] akshare.AuditNote / 巨潮API - 审计意见
[ ] akshare.StockInfoPledge - 股权质押

Day 3-4：企查查对比验证（仅1家公司）
[ ] 企查查API接入测试（1家公司：永新002014）
[ ] 验证免费数据覆盖率 ≥ 80% → 确认无需付费API

Day 5：手工补充 + 数据质量验收
[ ] 3项核心数据覆盖率验证（永新002014 + 康美/康得新）
[ ] 输出：数据源覆盖报告，确认是否需要企查查
```

**数据源配置化**：
```yaml
# config/governance_data_sources.yaml（新增）
data_sources:
  equity_structure:
    primary: {source: akshare, cost: 0, coverage: 0.95}
    paid_fallback: {source: qichacha, cost: 2000, coverage: 0.98}
  audit_opinions:
    primary: {source: cninfo, cost: 0, coverage: 1.0}
  equity_pledge:
    primary: {source: akshare, cost: 0, coverage: 0.85}
    paid_fallback: {source: qichacha, cost: 2000, coverage: 0.98}
```

---

*本文档由实施Agent起草，待评估Agent审查后执行。*
*G0Gate通过标准：评估Agent明确签字"通过"或"有异议但不影响执行"。*
