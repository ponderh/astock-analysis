# 模块8投资结论引擎 — 验收合同

**文档编号**: M8-VALIDATION  
**版本**: v1.0-draft  
**编写日期**: 2026-04-06  
**编写者**: 评估者（测试工程师）

---

## 一、模块定位回顾

### 1.1 在系统中的位置

模块8是A股深度分析系统的**最终输出层**，负责综合以下模块的输出，生成面向投资者的投资评级：

| 上游模块 | 输入内容 | 关键字段 |
|----------|----------|----------|
| 模块2财务 | ROE、营收增长、现金流、净现比 | `roe_latest`, `revenue_growth_yoy`, `net_cash_ratio` |
| 模块5红旗 | 红旗verdict、score、flag列表 | `verdict`, `overall_score`, `red_flags[]` |
| 模块6 MD&A | 战略分析、风险因素 | `key_themes`, `risk_factors` |
| 模块9治理 | 审计意见、股权质押、商誉 | `audit_opinions`, `pledge_ratio`, `goodwill_pct` |

### 1.2 输出规格

模块8应输出结构化投资结论：

```json
{
  "stock_code": "002014",
  "stock_name": "永新股份",
  "report_date": "2026-04-06",
  "rating": "买入|持有|卖出",
  "rating_confidence": 0.85,
  "rating_reason": "综合分析说明（200-500字）",
  "supporting_evidence": {
    "financial": "财务基本面摘要",
    "red_flags": "红旗信号摘要", 
    "mda": "MD&A战略摘要",
    "governance": "治理风险摘要"
  },
  "risk_warnings": ["风险提示列表"],
  "inputs_summary": {
    "financial_score": 85,
    "red_flag_verdict": "通过",
    "red_flag_score": 100,
    "mda_confidence": 0.7,
    "governance_signal": "正常"
  }
}
```

---

## 二、验收标准草案

### 2.1 正确性标准

| 编号 | 标准描述 | 验证方法 | 通过条件 |
|------|----------|----------|----------|
| C-01 | 评级输出合法性 | 检查输出JSON包含有效rating值 | rating ∈ {买入, 持有, 卖出, 待定} |
| C-02 | 置信度范围正确 | 检查confidence数值 | 0.0 ≤ confidence ≤ 1.0 |
| C-03 | 理由非空 | 检查rating_reason非空 | len(reason) ≥ 50 characters |
| C-04 | 输入溯源可查 | 验证inputs_summary包含所有上游模块的输入摘要 | 4个模块的输入摘要都存在 |
| C-05 | 评分逻辑自洽 | 当红旗score=100且财务指标正常时，不应输出"卖出" | 符合逻辑约束 |
| C-06 | 极端红旗处理 | 当存在EXTREME红旗时，rating不应为"买入" | 符合安全优先原则 |
| C-07 | 治理红灯处理 | 当存在非标审计意见时，rating应降级 | 符合治理门控逻辑 |

### 2.2 完整性标准

| 编号 | 标准描述 | 验证方法 | 通过条件 |
|------|----------|----------|----------|
| I-01 | 输出结构完整 | 检查JSON Schema | 包含所有必填字段（见下方Schema） |
| I-02 | 上游模块全覆盖 | 检查inputs_summary | 4个上游模块输入都有摘要 |
| I-03 | 支撑证据完整 | 检查supporting_evidence | 每个维度都有非空摘要 |
| I-04 | 风险提示存在 | 检查risk_warnings | 当存在风险时非空数组 |
| I-05 | 多维度覆盖 | 检查reason结构 | 至少包含财务、红旗、MD&A、治理中的3个维度 |

### 2.3 输出JSON Schema（必填字段）

```json
{
  "required": [
    "stock_code",
    "stock_name", 
    "report_date",
    "rating",
    "rating_confidence",
    "rating_reason",
    "supporting_evidence",
    "inputs_summary"
  ],
  "properties": {
    "stock_code": {"type": "string", "pattern": "^[0-9]{6}$"},
    "stock_name": {"type": "string"},
    "report_date": {"type": "string", "format": "date"},
    "rating": {"type": "string", "enum": ["买入", "持有", "卖出", "待定"]},
    "rating_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "rating_reason": {"type": "string", "minLength": 50},
    "supporting_evidence": {
      "type": "object",
      "required": ["financial", "red_flags", "mda", "governance"],
      "properties": {
        "financial": {"type": "string"},
        "red_flags": {"type": "string"},
        "mda": {"type": "string"},
        "governance": {"type": "string"}
      }
    },
    "risk_warnings": {"type": "array", "items": {"type": "string"}},
    "inputs_summary": {
      "type": "object",
      "required": ["financial_score", "red_flag_verdict", "red_flag_score", "mda_confidence", "governance_signal"],
      "properties": {
        "financial_score": {"type": "number"},
        "red_flag_verdict": {"type": "string"},
        "red_flag_score": {"type": "number"},
        "mda_confidence": {"type": "number"},
        "governance_signal": {"type": "string"}
      }
    }
  }
}
```

---

## 三、测试用例清单

### 3.1 功能正确性测试（必检）

| 用例ID | 描述 | 输入 | 预期输出 | 对应标准 |
|--------|------|------|---------|----------|
| TC-F-01 | 正常买入评级 | 财务score=85, 红旗verdict=通过(score=100), MD&A积极, 治理正常 | rating=买入 | C-01, C-05 |
| TC-F-02 | 持有评级（中性） | 财务score=50, 红旗verdict=存疑, MD&A中性 | rating=持有 | C-01 |
| TC-F-03 | 卖出评级（红旗问题） | 财务score=30, 红旗verdict=存疑, 存在RED flag | rating=卖出 | C-01, C-06 |
| TC-F-04 | 待定评级（数据缺失） | 财务score=N/A, 红旗verdict=超时, MD&A=N/A | rating=待定 | C-01 |
| TC-F-05 | 置信度边界-0 | 极端风险情况 | rating_confidence=0.0 | C-02 |
| TC-F-06 | 置信度边界-1 | 完美情况 | rating_confidence=1.0 | C-02 |
| TC-F-07 | 极端红旗拦截 | 存在EXTREME红旗 | rating≠买入 | C-06 |
| TC-F-08 | 非标审计意见处理 | 治理audit=非标 | rating降级 | C-07 |

### 3.2 完整性测试

| 用例ID | 描述 | 输入 | 预期输出 | 对应标准 |
|--------|------|------|---------|----------|
| TC-C-01 | 输出结构完整性 | 任意正常输入 | 包含所有必填字段 | I-01 |
| TC-C-02 | 上游输入溯源 | 任意正常输入 | inputs_summary完整 | I-02 |
| TC-C-03 | 支撑证据完整 | 任意正常输入 | 4维度证据齐全 | I-03 |
| TC-C-04 | 风险提示存在 | 有风险的输入 | risk_warnings非空 | I-04 |
| TC-C-05 | 理由多维度覆盖 | 任意输入 | reason覆盖3+维度 | I-05 |

### 3.3 场景回归测试

| 用例ID | 描述 | 测试股票 | 预期结果 |
|--------|------|---------|----------|
| TC-R-01 | 正常公司 | 永新股份(002014) | 评级应为买入或持有 |
| TC-R-02 | 财务异常 | 康美药业(600518) | 红旗score反映问题 |
| TC-R-03 | 退市风险 | 康得新(002450) | 识别为高风险 |
| TC-R-04 | ST股票 | *ST公司 | 降级处理 |
| TC-R-05 | 数据缺失场景 | 财务指标缺失 | 不崩溃，输出待定 |

### 3.4 集成测试（数据流）

| 用例ID | 描述 | 数据流 | 预期 |
|--------|------|--------|------|
| TC-I-01 | 模块2→模块8 | 财务数据正常传入 | 输出包含财务摘要 |
| TC-I-02 | 模块5→模块8 | 红旗verdict传入 | 输出包含红旗verdict |
| TC-I-03 | 模块6→模块8 | MD&A分析传入 | 输出包含战���摘要 |
| TC-I-04 | 模块9→模块8 | 治理信号传入 | 输出包含治理摘要 |
| TC-I-05 | 多模块联合 | 全部4个模块输入 | 综合评级正确 |

### 3.5 边界与异常测试

| 用例ID | 描述 | 异常情况 | 预期 |
|--------|------|----------|------|
| TC-E-01 | 输入超时 | 模块5超时 | 不阻塞，输出待定+reason说明 |
| TC-E-02 | 输入异常 | 模块2返回空 | 不崩溃，有降级逻辑 |
| TC-E-03 | 评级逻辑自相矛盾 | score=100但verdict=存疑 | 按保守原则处理 |
| TC-E-04 | 置信度计算溢出 | 输入极端值 | 严格限制在[0,1]区间 |

---

## 四、风险点清单

### 4.1 高风险（P0-必须关注）

| 风险ID | 风险描述 | 可能后果 | 缓解建议 |
|--------|----------|----------|----------|
| R-P0-01 | 多来源输入优先级冲突 | 红旗通过但财务不通过时，评级矛盾 | 设计明确优先级规则文档 |
| R-P0-02 | 置信度计算不透明 | 置信度与实际质量不匹配 | 输出置信度计算公式 |
| R-P0-03 | 评级逻辑泄露 | 过度依赖简单规则 | 保留人工复核接口 |

### 4.2 中风险（P1-需定义）

| 风险ID | 风险描述 | 可能后果 | 缓解建议 |
|--------|----------|----------|----------|
| R-P1-01 | 数据缺失时的降级策略不明确 | 评级质量下降 | 定义数据缺失时的默认行为 |
| R-P1-02 | MD&A文本过长时的处理 | 处理超时或截断信息丢失 | 定义摘要截断规则 |
| R-P1-03 | 多周期评级不一致 | 同一股票不同时期评级波动大 | 添加评级稳定性指标 |

### 4.3 低风险（P2-建议改进）

| 风险ID | 风险描述 | 影响 |
|--------|----------|------|
| R-P2-01 | 理由文本主观性 | 不同工程师生成的理由可能差异大 |
| R-P2-02 | 行业适应性 | 同一规则在不同行业效果不同 |

---

## 五、验收检查表

### 5.1 代码级检查

- [ ] 输出JSON Schema定义完整
- [ ] 评级枚举值正确（买入/持有/卖出/待定）
- [ ] 置信度计算有上界下界保护
- [ ] 4个上游模块输入接口就绪
- [ ] 异常处理分支覆盖

### 5.2 功能级检查

- [ ] 正常公司 → 买入 → 通过
- [ ] 高风险公司 → 卖出/待定 → 通过  
- [ ] 数据缺失场景 → 待定 → 通过
- [ ] 极端红旗 → 买入被拦截 → 通过

### 5.3 集成级检查

- [ ] 模块2数据流入模块8
- [ ] 模块5.verdict流入模块8
- [ ] 模块6分析流入模块8
- [ ] 模块9治理流入模块8
- [ ] 端到端评级生成

### 5.4 发布检查

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] 回归测试通过
- [ ] 性能测试（响应时间 < 5s for 正常输入）

---

## 六、后续工作

1. **实施者**需根据此验收方案实现模块8代码
2. **测试工程师**需编写自动化测试脚本验证每个TC用例
3. **架构师**需确认评级优先级规则并文档化

---

**验收状态**: 🟡 草稿完成，等待实施者反馈后定稿