# module6_mda - MD&A PDF解析管道

## 概述

永新股份(002014)原型验证实现，P0第3周任务。

**端到端成功率: 5/5 = 100%** ✅ (目标≥70%)

## 模块结构

```
module6_mda/
├── __init__.py         # 包入口
├── models.py           # 数据模型 (MDAResult, StageResult, etc.)
├── prompts.py          # LLM Prompt模板 (MDA_EXTRACTION_PROMPT等)
├── downloader.py       # PDF下载器 (5级降级策略)
├── extractor.py        # 文字提取器 (PyMuPDF/pdfplumber/PaddleOCR/Tesseract)
├── locator.py          # 章节定位器 (4级降级策略)
├── analyzer.py         # LLM分析器 + 规则降级分析器
├── scorer.py           # 质量评分器
├── pipeline.py         # 主协调器
└── test_yongxin.py     # 永新股份测试脚本
```

## 测试结果 (2020-2024年报)

| 年份 | 下载 | 提取 | 定位 | 分析 | 质量 |
|------|------|------|------|------|------|
| 2020 | ✅ | ✅ pymupdf | ✅ hierarchy(0.90) | ✅ rule_fallback | D(0.55) |
| 2021 | ✅ | ✅ pymupdf | ✅ hierarchy(0.90) | ✅ rule_fallback | C(0.61) |
| 2022 | ✅ | ✅ pymupdf | ✅ hierarchy(0.90) | ✅ rule_fallback | C(0.70) |
| 2023 | ✅ | ✅ pymupdf | ✅ hierarchy(0.90) | ✅ rule_fallback | B(0.77) |
| 2024 | ✅ | ✅ pymupdf | ✅ hierarchy(0.90) | ✅ rule_fallback | C(0.74) |

**注意**: LLM分析使用规则降级(RuleBasedAnalyzer)，因为DeepSeek API返回402 Payment Required (Insufficient Balance)。

## 技术要点

### 1. PDF下载 (5级降级)
- Level 1: curl直接下载 (处理brotli截断)
- Level 2: 换User-Agent + 更长超时
- Level 3: 分段下载 + Content-Length校验
- Level 4: 备用CDN节点
- **关键发现**: cninfo的brotli截断问题通过curl可以解决(requests不可)

### 2. 文字提取 (PyMuPDF优先)
- 2020-2024全部使用PyMuPDF成功提取
- 年报页数: 153-196页
- 字符数: 168K-199K字符(全文档)
- 定位到的MD&A章节: 1,950-6,311字符

### 3. 章节定位 (4级降级)
- 全部使用层级推断(LEVEL 2)成功
- 置信度: 0.90
- 使用编号模式(第一章/1./一.)检测章节边界

### 4. LLM分析 (DeepSeek API失败 → 规则降级)
- DeepSeek API返回402 (余额不足)
- 使用RuleBasedAnalyzer作为降级
- 提取: 战略承诺、关键主题、风险因素、经营亮点

## 运行方式

```bash
# 完整测试
python3 module6_mda/test_yongxin.py

# 单年报测试
python3 -c "
from module6_mda import MDAPipeline
p = MDAPipeline()
r = p.process_one_year(2024)
print(r.summary())
"
```

## 已知问题

1. **DeepSeek API 402**: API密钥余额不足，暂用规则分析降级
   - 解决: 需要充值或使用其他LLM API (Claude/Moonshot)
2. **语义得分偏低**: 规则分析器提取的战略信息有限，导致语义得分0.0
3. **2020年报MD&A较短**: 定位到的章节仅1,950字符，可能是因为层级推断边界问题

## 下一步

1. 解决LLM API问题 (充值DeepSeek或接入Claude)
2. 优化章节定位边界检测
3. 提高语义得分(依赖LLM正常工作)
4. 扩展到其他股票进行泛化测试
