# A股深度分析系统

A股上市公司财务分析系统，支持年报下载、财务数据获取、MD&A分析、图表生成、投资结论评分。

## 系统架构

```
┌─────────────────────────────────────────┐
│           模块1: PDF年报下载              │
│         (cninfo + 5级降级策略)            │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│          模块2: 财务数据获取              │
│           (akshare + HDF5缓存)            │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│          模块3: 文本提取                  │
│           (pdfplumber)                   │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│          模块4: 红旗规则引擎              │
│           (50+条财务规则)                 │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│          模块5: 图表生成                  │
│         (7类财务图表 + 仪表盘)            │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│          模块6: MD&A LLM分析              │
│      (MiniMax + DeepSeek双模型)          │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│          模块8: 投资结论引擎              │
│         (多维度评分 + 置信度)             │
└─────────────────────────────────────────┘
```

## 模块说明

| 模块 | 路径 | 功能 |
|------|------|------|
| 模块1 | module1_pdf/ | cninfo年报下载 |
| 模块2 | module2_financial/ | akshare财务数据 + HDF5缓存 |
| 模块3 | module3_text/ | pdfplumber文本提取 |
| 模块4 | module4_red_flags/ | 红旗规则引擎 |
| 模块5 | module5_charts/ | 7类财务图表生成 |
| 模块6 | module6_mda/ | MD&A LLM分析 |
| 模块7 | module7_announcements/ | 公告数据 |
| 模块8 | module8_investment_conclusion/ | 投资结论评分 |

## 漂移检测系统

独立模块，监控LLM分析系统的三类漂移：

- **LocateDriftDetector** - 章节定位漂移
- **RuleDriftDetector** - 规则一致性漂移
- **HallucinationDriftDetector** - LLM幻觉检测

详见 [drift_detection/](drift_detection/)

## 快速开始

### 1. 安装依赖

```bash
pip install akshare pandas pdfplumber matplotlib reportlab
pip install openai anthropic
```

### 2. 设置API密钥

```bash
export MINIMAX_API_KEY=your_minimax_key
export DEEPSEEK_API_KEY=your_deepseek_key
```

### 3. 运行端到端验证

```bash
cd impl
python3 e2e_final.py
```

## 端到端验证结果

测试标的：五粮液(000858)

| 阶段 | 状态 | 数据 |
|------|------|------|
| PDF下载 | ✅ | 4.4MB |
| 财务数据 | ✅ | 营收216→891亿，ROE 15%→24% |
| MD&A分析 | ✅ | MiniMax M2.7-highspeed |
| 图表生成 | ✅ | 6张图表 |
| 投资结论 | ✅ | 持有/50分/50%置信度 |

## 目录结构

```
impl/
├── e2e_final.py              # 端到端验证入口
├── module2_financial/
│   ├── api.py                 # 财务数据API
│   ├── adapter.py             # 数据格式转换
│   └── fetcher.py             # akshare封装
├── module5_charts/
│   ├── chart_generator.py     # 图表生成器
│   └── charts/                # 各类图表
├── module6_mda/
│   ├── downloader.py          # cninfo下载器
│   ├── extractor.py           # PDF文本提取
│   ├── locator.py             # MD&A定位
│   ├── analyzer.py            # LLM分析
│   └── prompts.py             # 分析prompt
├── module8_investment_conclusion/
│   ├── scoring_model.py        # 评分模型
│   ├── aggregator.py          # 数据聚合
│   └── investment_engine.py   # 投资引擎
└── drift_detection/           # 漂移检测系统
    ├── models.py              # 数据模型
    ├── database.py            # SQLite存储
    ├── detectors_locate.py    # 定位检测
    ├── detectors_rule.py      # 规则检测
    ├── detectors_hallucination.py  # 幻觉检测
    ├── alerts.py              # 告警系统
    └── monitor.py             # 监控器
```

## 注意事项

1. **API密钥**: 所有密钥通过环境变量设置，不要硬编码
2. **年报数据**: 年报通常在4月底发布，测试时注意年份范围
3. **数据源**: 财务数据依赖akshare，LLM分析依赖MiniMax/DeepSeek API
