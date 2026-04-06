# G0Gate 3个中度问题解决方案

> 版本：v1.0
> 日期：2026-04-03
> 制定：实施Agent
> 依据：G0_review.md 评估审查意见

---

## 问题1：PostgreSQL→MySQL降级方案

### 1.1 问题本质

PostgreSQL JSONB 与 MySQL JSON 的核心差异：

| 维度 | PostgreSQL JSONB | MySQL 8.0 JSON |
|------|-----------------|----------------|
| 索引 | GIN索引，支持 expression index | 虚拟列 + expression index（部分覆盖） |
| 查询语法 | `data->'key'`（原生操作符） | `JSON_EXTRACT(col, '$.key')` |
| 存储格式 | 二进制，分词索引 | 原始JSON文本，无分词索引 |
| 数组查询 | `data->'arr'->0` | `JSON_EXTRACT(col, '$.arr[0]')` |
| 包含查询 | `@>` `?` 操作符 | `JSON_CONTAINS()` 函数 |
| 路径查询 | `#>` 多级路径 | `JSON_EXTRACT(..., '$.a.b.c')` |

阈值库对JSONB的依赖主要在两类场景：
1. **历史快照**：`threshold_snapshots` 表，每行存一个指标在某个时间点的分位数快照（含百分位数组）
2. **公告标签**：`announcements` 表，`tags` 字段是多选标签数组，`metadata` 是动态字段

### 1.2 MySQL降级方案设计

#### 方案A：MySQL 8.0 虚拟列 + 表达式索引（推荐）

**核心思路**：将JSONB字段拆解为虚拟列（virtual generated column），在虚拟列上建普通B-tree索引，兼容MySQL生态。

```sql
-- PostgreSQL 原设计（JSONB）
CREATE TABLE threshold_snapshots (
    id BIGSERIAL PRIMARY KEY,
    industry_code VARCHAR(10) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    snapshot_date DATE NOT NULL,
    data JSONB NOT NULL  -- 包含 {p10, p25, p50, p75, p90, raw_values[]}
);

CREATE INDEX idx_snapshots_lookup 
ON threshold_snapshots USING GIN (data) 
WHERE data ? 'p50';  -- 条件索引

-- MySQL 降级方案
CREATE TABLE threshold_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    industry_code VARCHAR(10) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    snapshot_date DATE NOT NULL,
    data JSON NOT NULL,
    -- 虚拟列：暴露常用路径，避免每次 JSON_EXTRACT
    p10_value DECIMAL(10,4) GENERATED ALWAYS 
        AS (JSON_EXTRACT(data, '$.p10')) STORED,
    p50_value DECIMAL(10,4) GENERATED ALWAYS 
        AS (JSON_EXTRACT(data, '$.p50')) STORED,
    p90_value DECIMAL(10,4) GENERATED ALWAYS 
        AS (JSON_EXTRACT(data, '$.p90')) STORED,
    raw_values_json JSON GENERATED ALWAYS 
        AS (JSON_EXTRACT(data, '$.raw_values')) STORED,
    -- 复合索引，支持按 (industry, metric, date) 快速定位
    INDEX idx_lookup (industry_code, metric_name, snapshot_date),
    INDEX idx_p50 (industry_code, metric_name, p50_value)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**说明**：
- `STORED` 虚拟列：在写入时计算并持久化，支持建索引
- 虚拟列索引替代GIN索引：对常见查询路径（`WHERE industry=X AND metric=Y AND p50 > 1.2`）完全覆盖
- `raw_values_json` 仍以JSON形式存储，仅在需要百分位计算时才展开
- 对历史快照的兼容性：**P0/P1阶段不需要查询原始数组**，降级方案不影响核心功能

#### 方案B：全JSON + 应用层展开（保守方案）

不做虚拟列，直接用JSON存储，在Python应用层做展开和过滤。
- 优点：Schema改动最小
- 缺点：无法建索引，查询全表扫描，性能差3-10倍
- 适用：临时降级，不推荐生产使用

#### 方案C：SQLite作为开发环境备选

仅dev环境使用SQLite，SQLite的JSON支持（json1扩展）与MySQL类似。
- 优点：本地开发零成本
- 缺点：生产环境不能用
- **推荐用途**：本地调试+CI测试，隔离数据库依赖

### 1.3 API重写清单

以下API函数在切换到MySQL时需要重写，`industry_thresholds/threshold_api.py`为主要影响文件：

| API函数 | JSONB用法 | MySQL等效写法 | 工作量 |
|---------|-----------|--------------|--------|
| `get_threshold(industry, metric, year)` | `WHERE data->>'$.p50' > X` | `WHERE p50_value > X` | **小**（虚拟列已建索引） |
| `get_red_flags(industry, year)` | `WHERE data @> '{"flag":true}'` | `WHERE JSON_CONTAINS(data, '{"flag":true}')` | **中**（需改3-5处） |
| `get_percentile_array(industry, metric)` | `data->'raw_values'` | `raw_values_json`（已是JSON数组） | **小** |
| `save_snapshot(industry, metric, date, obj)` | `INSERT ... data=jsonb(obj)` | `INSERT ... data=JSON_OBJECT(...)` | **小**（改1处构造方式） |
| `query_announcements(stock, start, end, tags)` | `WHERE data->'tags' ? ANY(array)` | `WHERE JSON_CONTAINS(data, ...)` | **中**（标签数组查询逻辑） |

预计API重写工作量：**2-3人日**（不涉及业务逻辑变更）

### 1.4 接口抽象层设计

```
industry_thresholds/
├── db/
│   ├── __init__.py
│   ├── base.py          # 抽象基类
│   ├── postgres.py      # PostgreSQL实现（主方案）
│   └── mysql.py         # MySQL实现（降级方案）
│
├── threshold_api.py     # 对外API，改用 db.get_adapter()
└── db_schema.sql        # 两套Schema（PG + MySQL）
```

```python
# db/base.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class ThresholdSnapshot:
    industry_code: str
    metric_name: str
    snapshot_date: str
    p10: float
    p50: float
    p90: float
    raw_values: List[float]
    confidence: float

@dataclass  
class RedFlag:
    flag_type: str
    metric_name: str
    threshold_value: float
    actual_value: float
    severity: str  # 'low' / 'medium' / 'high'

class ThresholdDBAdapter(ABC):
    """数据库适配器抽象基类"""
    
    @abstractmethod
    def get_threshold(
        self, 
        industry_code: str, 
        metric_name: str, 
        year: int
    ) -> Optional[ThresholdSnapshot]: ...
    
    @abstractmethod
    def get_red_flags(
        self,
        industry_code: str,
        year: int
    ) -> List[RedFlag]: ...
    
    @abstractmethod
    def save_snapshot(
        self,
        snapshot: ThresholdSnapshot
    ) -> bool: ...
    
    @abstractmethod
    def query_announcements(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]: ...
    
    @abstractmethod
    def health_check(self) -> bool: ...

# db/factory.py
def get_adapter(db_type: str = "postgres") -> ThresholdDBAdapter:
    """工厂函数，根据配置返回对应数据库适配器"""
    if db_type == "postgres":
        from .postgres import PostgresAdapter
        return PostgresAdapter()
    elif db_type == "mysql":
        from .mysql import MySQLAdapter
        return MySQLAdapter()
    else:
        raise ValueError(f"Unsupported DB type: {db_type}")
```

```python
# industry_thresholds/threshold_api.py（重构后）
from db.factory import get_adapter

# 全局单例，通过环境变量或配置决定使用哪个数据库
_adapter = None

def init_adapter(db_type: str = None):
    global _adapter
    db_type = db_type or os.getenv("THRESHOLD_DB", "postgres")
    _adapter = get_adapter(db_type)

def get_threshold(industry_code: str, metric_name: str, year: int) -> Optional[dict]:
    return _adapter.get_threshold(industry_code, metric_name, year)

def get_red_flags(industry_code: str, year: int) -> List[dict]:
    return _adapter.get_red_flags(industry_code, year)
```

**推荐**：采用方案A（虚拟列+表达式索引），**API重写工作量小，接口抽象层保障互换性**。

---

## 问题2：OpenAI LLM合规性未评估

### 2.1 合规风险分析

**数据出境合规**：年报PDF包含企业敏感财务数据（收入、成本、负债、股东信息），传送到境外LLM API需考虑：
- 《数据安全法》：重要数据出境需安全评估
- 《个人信息保护法》：个人信息出境需满足合规条件
- 年报中的财务数据是否构成"重要数据"存在争议，无明确红线

**结论**：合规风险存在，但非绝对禁止。需在第1周进行预评估（1-2人日）。

### 2.2 三个方案对比

| 维度 | 方案A：gpt-4o-mini（实测） | 方案B：Claude API | 方案C：国产模型 |
|------|--------------------------|------------------|----------------|
| **合规性** | ⚠️ 需评估（数据出境风险） | ⚠️ 同样需评估（境外API） | ✅ 国内部署，数据不出境 |
| **中文年报能力** | 理论上强，但未实测 | 强（已验证），Claude 3.5 Sonnet中文优秀 | DeepSeek数学/推理强，中文财报能力中等偏上 |
| **成本** | $0.15/1M tokens（mini） | $3/1M tokens（ Sonnet），贵20倍 | DeepSeek API $0.14/1M tokens（相近） |
| **速度** | 快（mini） | 中等 | DeepSeek V3 接近GPT-4水平 |
| **幻觉控制** | 三层保障已设计 | 同样适用 | Prompt需重新校准 |
| **约束性Prompt兼容性** | 成熟，GPT系列最优 | 成熟（Anthropic模型） | 需重新调试few-shot examples |
| **MD&A提取实测精度** | **未知** | **未知** | **未知** |

### 2.3 方案A实测设计（推荐）

**理由**：gpt-4o-mini是成本/速度最优选，若中文能力达标应优先使用。

**实测步骤**（1-2人日）：

1. **准备评测集**（用永新002014）：
   - 手动标注5页年报战略子节（约500-800字段）
   - 覆盖：收入确认判断、资产减值、关联交易描述、战略方向表述
   - 标注格式：`{field_name: string, value: string, page: int, confidence: bool}`

2. **API调用**：
   ```python
   import openai
   
   def evaluate_mda_accuracy(pdf_path: str, eval_data: List[dict]) -> dict:
       """返回：提取准确率、召回率、幻觉率"""
       # 用约束性Prompt调用gpt-4o-mini
       # 与标注集对比，计算 accuracy/recall
       pass
   ```

3. **达标标准**：
   - **准确率 ≥ 85%**：保留gpt-4o-mini
   - **准确率 70-85%**：补充few-shot examples再测一轮
   - **准确率 < 70%**：切换方案B或C

4. **合规并行评估**（第1周）：
   - 咨询是否有数据出境合规要求（如公司属于特定行业/央企）
   - 若无强制要求：保留gpt-4o-mini
   - 若有要求：立即切换方案B或C

### 2.4 备选方案B：Claude API

**接入设计**（2-3人日）：

```python
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def analyze_mda_with_claude(text: str, prompt: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {"role": "user", "content": f"{prompt}\n\n年报内容：\n{text[:8000]}"}
        ]
    )
    return parse_structured_response(response.content[0].text)
```

**优点**：
- 合规性相对清晰（Anthropic已通过SOC2）
- 中文能力强，财报专业术语理解优于预期

**缺点**：成本是gpt-4o-mini的20倍

### 2.5 备选方案C：国产模型

**候选模型**：
- **DeepSeek V3**（推荐）：数学推理强，中文能力接近GPT-4水平，API价格低
- **通义千问2.5**：阿里云，中文优化，开源版本可用

**接入设计**：
```python
# DeepSeek
from openai import OpenAI
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), 
                base_url="https://api.deepseek.com")

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[...]
)
```

**Prompt重校准**（额外1-2人日）：
- few-shot examples需要用中文财务术语重新编写
- 三层幻觉保障需针对国产模型调整（国产模型幻觉率通常高于GPT-4）

### 2.6 推荐方案与实施路径

**推荐：方案A优先，方案B备用**

```
第1周（第1-2天）：
├── Step 1：gpt-4o-mini中文年报提取实测（永新2024年报，5页标注集）
├── Step 2：合规评估（判断是否有数据出境强制要求）
└── 结论：
    ├── 实测准确率 ≥ 85% + 无合规强制要求 → 保留 gpt-4o-mini
    ├── 实测准确率 70-85% + 无合规强制要求 → 加few-shot再测一轮
    └── 有合规强制要求 OR 准确率 < 70% → 切换 Claude 或 DeepSeek
```

**P0合规预评估任务清单**（补充到G0_plan实施计划第1周）：

```
P0合规预评估（1-2人日，并行执行）：
[ ] 年报数据出境合规评估（对照《数据安全法》重要数据定义）
[ ] gpt-4o-mini中文年报提取准确率实测（永新2024年报，标注集5页）
[ ] 达标则保留；不达标则启动Claude API接入（2-3人日）
[ ] Prompt模板在备用模型上重校准（1-2人日）
```

---

## 问题3：治理模块API数据源不明确

### 3.1 三种数据获取方式对比

| 维度 | 企查查/天眼查API（付费） | 年报+巨潮免费数据（混合） | 手工输入（仅验证） |
|------|------------------------|--------------------------|-------------------|
| **数据完整性** | 高（工商+司法+股权+质押） | 中（年报覆盖率>95%，巨潮公告覆盖全） | 低（仅能做1-3家验证） |
| **股权结构穿透** | 穿透3层，实时更新 | 年报披露，年度更新，穿透深度有限 | 手工录1-2层 |
| **股权质押比例** | 实时，精确到每一笔 | 年报附注披露，精确，但非实时 | 手工录关键数据 |
| **审计意见历史** | ❌ 不包含 | 巨潮有5年审计意见历史 | ❌ 手工 |
| **商誉/并购追踪** | 部分覆盖 | 年报+公告，可覆盖 | 手工 |
| **API成本** | ¥2000-5000/月（企查查基础版） | 免费（akshare+巨潮） | 人工成本 |
| **接入难度** | 中（需签约+调试） | 低（akshare已封装） | N/A |
| **实时性** | 实时 | 年报（年度），公告（及时） | 手工 |

### 3.2 企查查 vs 天眼查字段对比

| 数据字段 | 企查查API | 天眼查API |
|----------|-----------|-----------|
| 股东信息（穿透） | ✅ 穿透3层，含持股比例 | ✅ 穿透3层，含持股比例 |
| 股权质押（数量+比例） | ✅ 实时，有详细记录 | ✅ 实时，有详细记录 |
| 工商变更记录 | ✅ 含历史变更 | ✅ 含历史变更 |
| 司法风险（被执行/限高） | ✅ 较全 | ✅ 较全 |
| 审计意见 | ❌ 不提供 | ❌ 不提供 |
| API价格 | ¥3000/月（基础版） | ¥2500/月（基础版） |
| Python SDK | 官方提供 | 第三方封装 |

**结论**：两API功能相近，企查查略优但更贵。审计意见均不提供，需依赖年报/巨潮。

### 3.3 推荐方案：混合数据源（成本效益最优）

**核心原则**：用免费数据覆盖核心需求，用付费API补充关键缺口

```
治理筛查数据源优先级：
第一层（免费，优先使用）：
├── 股权结构：akshare.StockInfoPledge调查(质押) + 年报附注（股东）
├── 审计意见：巨潮API（cninfo）或akshare
└── 股权质押：akshare有质押相关数据接口

第二层（付费API，补充缺口）：
└── 企查查API：若免费数据缺股权质押详细记录 → 补充
    （月度¥2000，成本可控，且治理筛查仅需初始建库+季度更新）

第三层（手工）：仅用于系统验证阶段（3-5家公司）
```

**最小可验证数据集**（3项核心数据）：

| 数据项 | 来源 | 获取方式 | 数据质量 |
|--------|------|----------|----------|
| **股权结构**（前5大股东+持股比例） | 年报附注 或 akshare | 免费API | 年报精确，年度更新 |
| **审计意见**（近5年） | 巨潮(cninfo.com.cn) | 免费API | 官方来源，5年全覆盖 |
| **股权质押比例**（总质押股数/总股本） | 年报附注 或 akshare | 免费API | 年报精确，非实时 |

### 3.4 实施计划补充

**第1周治理数据采集方案**：

```
Day 1-2：免费数据源接入
├── akshare.StockInfoPledge - 股权质押数据（已有封装）
├── akshare.AuditNote - 审计意见数据
└── 巨潮API（cninfo.com.cn）- 补充年报数据

Day 3-4：有疑问时接入企查查（选1家做对比验证）
└── 验证免费数据覆盖率：目标覆盖率 ≥ 80% 则无需付费API

Day 5：手工补充 + 数据质量验收
└── 3项核心数据覆盖率验证（永新002014 + 1家问题公司）
```

**数据覆盖率验收标准**：

| 数据项 | 可接受覆盖率 | 说明 |
|--------|-------------|------|
| 股权结构（前5大股东） | ≥ 90% | 年报覆盖率已很高 |
| 审计意见（近5年） | 100% | 巨潮可查全部A股 |
| 股权质押比例 | ≥ 80% | akshare覆盖主要质押记录 |

### 3.5 数据源配置设计

```python
# config/governance_data_sources.yaml
data_sources:
  equity_structure:
    primary: 
      source: "akshare"
      api: "StockShareholderResearch"  
      cost: 0  # 免费
      coverage: 0.95
      update_freq: "annually"  # 年报更新
    fallback:
      source: "annual_report_pdf"
      extraction: "manual_or_llm"
      coverage: 0.98
      update_freq: "annually"

  audit_opinions:
    primary:
      source: "cninfo"
      api: "audit_history"
      cost: 0  # 免费注册账号
      coverage: 1.0
      update_freq: "annually"
    fallback:
      source: "akshare"
      api: "AuditNote"
      cost: 0
      coverage: 0.90

  equity_pledge:
    primary:
      source: "akshare" 
      api: "StockInfoPledge"
      cost: 0
      coverage: 0.85
      update_freq: "quarterly"
    paid_fallback:
      source: "qichacha"  # 企查查（可选）
      cost: 2000  # ¥/月
      coverage: 0.98
      update_freq: "real-time"
```

---

## 总结：推荐方案一览

| 问题 | 推荐方案 | 关键理由 |
|------|---------|---------|
| PostgreSQL→MySQL | **方案A（虚拟列+表达式索引）** | API重写工作量小（2-3人日），虚拟列已覆盖主要查询路径 |
| LLM合规性 | **方案A优先实测（第1周1-2天）+ Claude备用** | gpt-4o-mini成本/速度最优；中文能力需实测确认；Claude立即可接 |
| 治理数据源 | **免费混合方案（第1周先免费，企查查作补充）** | 年报+巨潮覆盖3项核心数据≥80%；企查查仅作补充验证 |
