# P1-1 估值分析引擎 — 最终实施协议

**日期**: 2026-04-04
**参与方**: 管控者、估值专家、实施者、评估者、质疑者
**状态**: 协议已裁决，实施者请按此执行

---

## 裁决摘要

### 质疑者挑战结果（采纳情况）

| 质疑 | 采纳 | 裁决 |
|------|------|------|
| ① 行业分类错误是系统性的，仅校验不够 | ✅ 采纳 | 弃用硬路由，改为置信度评分+多方法加权 |
| ② 制度断裂免责声明是工程惰性 | ✅ 采纳 | 数据打regime标签，regime-aware分位计算 |
| ③ DCF是点估计而非范围估计 | ✅ 采纳 | DCF必须输出三档（乐观/基准/悲观），非点估计 |
| ④ 银行PB调整机制工程上不可行 | ✅ 采纳 | Phase 1不做调整，仅原始PB与行业均值比较 |
| ⑤ 格雷厄姆数降级约束无法靠文档执行 | ✅ 采纳 | 结构化字段标记 + verdict双轨 + 默认排除出综合信号 |

---

## 架构决策（最终版）

### 核心原则

```
1. PB是A股主估值锚，PE为辅
2. DCF是范围估计工具，非点估计
3. 格雷厄姆数是安全边际测试，不是估值锚
4. 行业路由是软置信度，不是硬拦截
5. 历史分位必须打regime标签
```

### 架构图

```
行业分类（SW3）
      ↓
[置信度评分] ──→ 多方法加权输出
      ↓
┌─────────────────────────────────────┐
│  PE/PB分位（regime-aware）           │  ← 主方法
│  DCF三档（乐观/基准/悲观）            │  ← 辅助
│  格雷厄姆（安全测试，隔离输出）        │  ← 极端检测
│  银行PB（无调整，仅原始值）           │  ← 简化处理
└─────────────────────────────────────┘
      ↓
[综合信号]（格雷厄姆默认排除）
      ↓
[数据质量门控]（regime断裂警告+置信度）
```

---

## 实施要求（强制）

### 1. 行业路由：软置信度替代硬拦截

**禁止**：
- 硬编码 `if bank → pb_only`
- 单一行业代码直接路由到单一方法

**必须实现**：
- 行业置信度评分：`get_industry_confidence(stock_code)` → 0~1
- 多业务加权：主营构成比例 × 各行业阈值
- 当置信度 < 0.6 时，`industry_flag = "low_confidence"`，所有行业调整结果降权50%

### 2. 历史分位：regime-aware计算

**禁止**：
- 直接用全量历史数据算分位，不打标签

**必须实现**：
- 数据打标签：`regime` ∈ {pre-split-share, post-split-share, post-full-circulation, registration-system}
- 默认使用 registration-system（2020+）后数据
- 双窗口输出：`percentile_full`（全量）和 `percentile_recent`（注册制后）
- 两者差异 > 20% → 触发 `regime_discontinuity_warning: true`

### 3. DCF：必须输出三档

```json
{
  "dcf": {
    "confidence": "low",
    "regime": "range_estimate",
    "intrinsic_pessimistic": 12.5,
    "intrinsic_central": 18.2,
    "intrinsic_optimistic": 24.8,
    "confidence_width_pct": 68,
    "note": "三档宽度>当前股价50%，置信度降为low"
  }
}
```

**当三档宽度 > 当前股价50%时**：
- `confidence` 自动降为 `low`
- 该方法**不参与综合信号加权**（权重归零）
- 输出 `dcf_over_width_threshold: true`

### 4. 格雷厄姆数：结构性隔离

**必须实现**：
- 字段标记：`graham_number` → `is_safety_test: true`（非估值锚）
- verdict双轨：
  - `overall_verdict`：格雷厄姆数**默认排除**
  - `graham_verdict`：格雷厄姆数独立输出
- 综合信号权重：格雷厄姆数默认权重 = 0

### 5. 银行PB：Phase 1无调整

**必须实现**：
- 仅输出原始PB与行业均值的比较
- 不引入任何不良率/拨备覆盖率调整（数据缺口未解决前禁止引入）
- 明确标注：`bank_pb_adjusted: false, note: "Phase1不含信用风险调整"`

### 6. 行业阈值库扩展

**必须实现**：
- 扩展现有 `indicator_thresholds` 表，新增 `PE` 和 `PB` 两个指标的分位数存储
- 不新建表（避免重复建设）
- PE/PB的red_flag阈值按行业动态计算（P20=低估，P80=高估）

---

## 验收标准（评估者必须逐项检查）

| # | 验收项 | 判定条件 |
|---|--------|---------|
| V1 | regime-aware分位 | 计算10年全量和注册制后两组分位，差异>20%时有警告 |
| V2 | DCF三档输出 | 三档均存在，且宽度=0时触发数据错误告警 |
| V3 | DCF超宽降权 | 三档宽度>50%时，confidence=low且权重归零 |
| V4 | Graham结构隔离 | overall_verdict不含格雷厄姆数；graham_verdict独立存在 |
| V5 | Graham字段标记 | `is_safety_test: true` 存在且正确 |
| V6 | 银行PB无调整 | 无任何不良率/拨备调整字段；原始PB与行业均值对比 |
| V7 | 行业软路由 | 置信度<0.6时降权50%，不硬拦截 |
| V8 | 数据质量门控 | 有效方法<2时 → verdict="数据不足" |
| V9 | 单元测试 | 永新(002014)、招商银行(600036)、平安(601318)各一只通过 |
| V10 | 集成测试 | module2(财务)+industry_thresholds(行业)+valuation_engine 三方联调 |

---

## 实施者任务分解

### 阶段1（Day 1-2）：基础设施

- [ ] `models.py`：ValuationBlock dataclass，含regime字段、三档DCF、Graham隔离标记
- [ ] `industry_thresholds/api.py`扩展：PE/PB分位数查询，regime参数
- [ ] `regime_classifier.py`：regime标签逻辑，registration-system后数据优先

### 阶段2（Day 3-4）：核心方法

- [ ] `methods/pe_pb_percentile.py`：regime-aware分位，双窗口，差异警告
- [ ] `methods/dcf.py`：三档输出，超宽自动降权
- [ ] `methods/graham.py`：安全测试模式，隔离标记
- [ ] `methods/bank_pb.py`：无调整版，仅原始PB+行业均值

### 阶段3（Day 5-6）：集成

- [ ] `engine.py`：置信度评分，行业软路由，格雷厄姆隔离
- [ ] `api.py`：统一入口，输出verdict双轨
- [ ] 单元测试（3只股）
- [ ] 集成测试

### 阶段4（Day 7-8）：验证

- [ ] 全量回归（永新/招商/平安）
- [ ] 评估者V1-V10逐项检查
- [ ] 修正评估者发现的问题

---

## 开放问题（已裁决）

| 问题 | 裁决 |
|------|------|
| DCF权重 | 动态：超宽时归零，正常时≤20% |
| PE/PB基准池 | 注册制后（2020+）为默认，历史数据仅作参考 |
| 格雷厄姆数版本 | 原版（22.5系数），不修正 |
| 行业阈值表 | 扩展现有表，不新建 |

---

## 质量门控红线（任何一项触发则不允许上线）

1. DCF输出单点估计（而非三档）→ **禁止上线**
2. 格雷厄姆数进入综合信号默认权重 → **禁止上线**
3. 银行PB含任何调整参数 → **禁止上线**
4. 历史分位无regime标签 → **禁止上线**
5. 行业硬路由（if bank → ...） → **禁止上线**
