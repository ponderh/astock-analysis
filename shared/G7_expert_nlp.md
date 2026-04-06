# G7 NLP/LLM专家意见

## 方案评估

### 1. 统一Schema的方案是否合理？

**结论：合理，但需要针对性调优。**

Schema A（`MDA_EXTRACTION_PROMPT`）的JSON结构（commitments/themes/risks/highlights四件套）是下游规约的事实标准，Schema B（product/market/technology/capacity四维度）是中间层语义结构。二者语义容量不同，直接替换不会导致信息丢失——因为战略子节的内容本来就能映射到Schema A的字段。

关键问题不在"能不能统一"，而在"Schema A的Prompt措辞是否适合短文本（strategy subsection）"。

### 2. MDA_EXTRACTION_PROMPT是否太宽泛？

**结论：约束足够，但有一处隐患。**

Schema A第6条Hard Constraint明确写了：
> "仅提取战略子节内容，不要扩展到其他章节"

这条约束从Prompt工程角度是**有效的**，LLM会遵循。但需要注意的是，Schema A中有多处"原文第X段"的段落引用要求——当输入是截取后的战略子节时，"第X段"指的是**截取文本内部**的段落序号，而非原文档的真实段落号。这会导致引文格式与文档其余部分不一致。建议将"原文第X段"改为"本段"或"战略子节第X段"，避免引用歧义。

### 3. 有没有更优的中间方案？

**结论：有，但成本收益比不高。**

可以考虑的中间方案：
- **方案C（Schema C）**：设计一个同时兼容两种场景的中间Schema，同时包含Schema A和Schema B的字段，下游按需读取。但这样Schema B的`confidence_level`等字段对下游无意义，属于过度设计。
- **方案D（两阶段提取）**：先用Schema B提取结构化摘要，再映射到Schema A。但增加了LLM调用次数和延迟，不值得。
- **方案E（Schema A增强版）**：在Schema A基础上增加`strategy_dimensions`字段（融合Schema B的四维度），作为Schema A的自然扩展。这样既满足下游期望，又保留了对战略子节特定维度的捕捉能力。

实际上，**Schema A统一方案是最优解**，原因：
1. 消除幻觉告警的根本原因是字段对齐，而非Schema设计
2. Schema A本身已包含战略主题（theme）这一高语义抽象层，可以承载产品/市场/技术/产能的战略描述
3. Schema B的`confidence_level`可降级为元数据，不影响核心Schema

---

## 建议方案

### 统一Schema：战略子节调用改用Schema A（增强版）

**具体改动（三处）：**

#### 改动1：调整`MDA_EXTRACTION_PROMPT`（prompts.py）

修改段落引用措辞，避免跨文档歧义：

```
# 原文
"每个字段必须附带原文引文：[原文第X段] "...""

# 改为
"每个字段必须附带原文引文：[战略子节第X段] "...""
```

#### 改动2：增强`MDA_EXTRACTION_PROMPT`的领域适配性

在`key_strategic_themes`描述中，增加对战略维度（产品/市场/技术/产能）的显式引导，让LLM在分析战略子节时主动捕捉这些维度：

```
在`description`字段中，如涉及以下维度请明确标注：
- 产品战略（如新产品、技术路线）
- 市场战略（如目标客户、市场份额）
- 技术战略（如研发投入、技术路线）
- 产能战略（如扩产计划、产能利用率）
```

#### 改动3：修改`analyzer.py`中的`analyze_strategy_section()`

```python
# analyze_strategy_section() 改调用 MDA_EXTRACTION_PROMPT
def analyze_strategy_section(self, strategy_text: str) -> Dict[str, Any]:
    try:
        from .prompts import MDA_EXTRACTION_PROMPT
    except ImportError:
        from prompts import MDA_EXTRACTION_PROMPT

    return self.analyze(
        text=strategy_text,
        prompt_template=MDA_EXTRACTION_PROMPT,
        output_schema={},
        max_tokens=8192  # 从4096提升，应对Schema A更大的输出量
    )
```

#### 改动4：调整`_check_hallucination`中的字段检测

由于Schema A的`operating_highlights`在纯战略子节场景下可能为空（战略子节通常不含经营指标），需要将该字段从必检列表中移除：

```python
# analyzer.py _check_hallucination()
required_fields = ['strategic_commitments', 'key_strategic_themes', 'risk_factors']
# operating_highlights 已从必检列表移除，因为战略子节通常不包含经营指标
```

---

## 潜在风险

### 风险1：Schema A输出量显著大于Schema B
**影响**：LLM响应可能超token限制
**缓解**：将`max_tokens`从4096提升至8192；保持`strategy_text`截断在5000字
**严重程度**：低

### 风险2：战略子节中`risk_factors`和`operating_highlights`可能大量为空
**影响**：这些字段输出"NONE"，下游展示层需要做空值处理
**缓解**：在pipeline或下游做空值过滤，不将这些空字段计入幻觉告警
**严重程度**：低

### 风险3：段落引用格式跨文档不一致
**影响**：引文格式"战略子节第X段"与年报其他部分"原文第X段"风格不统一
**缓解**：在文档处理阶段统一归一化为段内序号，不暴露"战略子节"字样给下游
**严重程度**：中（需下游配合）

### 风险4：Schema A的Prompt优化方向是全MD&A，对战略子节特定维度（产品/市场/技术/产能）引导不足
**影响**：LLM可能提取到战略承诺但忽略产品/市场等维度描述
**缓解**：在Prompt的`key_strategic_themes`部分增加维度引导（见改动2），引导LLM在主题识别时覆盖这四个维度
**严重程度**：中（需实测验证）

### 风险5：回归测试（永新股份2020-2024）可能出现历史数据格式兼容问题
**影响**：历史分析结果使用Schema B，新Schema A结果字段名称不同，无法直接对比
**缓解**：建立双Schema映射表，或在回归测试中使用JSON deep-diff而非字段对齐比较
**严重程度**：中

---

## 总结优先级

| 优先级 | 动作 | 理由 |
|--------|------|------|
| P0 | 修改`analyzer.py`中`analyze_strategy_section()`调用Schema A | 根因修复，消除幻觉告警 |
| P1 | 调整Prompt中段落引用措辞 | 避免引文歧义 |
| P1 | 移除`operating_highlights`从必检字段 | 战略子节场景适配 |
| P2 | 增加战略维度引导词到Prompt | 提升战略子节特定维度的提取质量 |
| P2 | 提升`max_tokens`至8192 | 防止Schema A大输出截断 |
| P3 | 回归测试双Schema映射表 | 永新股份历史数据兼容 |
