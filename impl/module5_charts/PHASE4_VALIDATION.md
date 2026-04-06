# Phase 4 验收方案

**文档编号**: P1-M5-VALIDATION-P4  
**版本**: v1.0  
**创建日期**: 2026-04-06  
**测试工程师**: 测试专家  
**状态**: 待验收

---

## 一、验收范围

Phase 4 涵盖 **3张MD&A可视化图表** 的验收测试：

| 序号 | 图表名称 | 类型 | 数据源 | 优先级 |
|------|----------|------|--------|--------|
| 12 | 管理层讨论要点词云 | 词云(WordCloud) | 模块6 | P2 |
| 13 | 经营风险趋势 | 时间线(Timeline) | 模块6 | P1 |
| 14 | 行业环境评估雷达 | 雷达图(Radar) | 模块6 | P1 |

---

## 二、验收标准

### 2.1 功能验收

| 验收项 | 验收条件 | 测试方法 |
|--------|----------|----------|
| 词云库使用 | 图表12使用 `wordcloud` 库生成 | 代码检查 |
| 中文标签 | 中文标签正确显示，无乱码 | 图表目视检查 + 字体配置验证 |
| PNG格式 | 分辨率≥150dpi，文件名规范 | 文件属性检查 + 正则验证 |
| 数据加载 | 使用 `mda_loader.py` 加载模块6数据 | 代码检查 + 数据追踪 |
| 图表完整性 | 3张图表全部成功生成 | 文件存在性检查 |

### 2.2 质量验收

| 验收项 | 验收条件 | 标准 |
|--------|----------|------|
| 词云效果 | 词频合理，中文分词正确 | 目视检查词云输出 |
| 时间线 | 年份排序正确，标注清晰 | 数据验证 |
| 雷达图 | 5个维度完整，比例协调 | 维度完整性检查 |
| 文件大小 | PNG文件 > 10KB | 文件大小验证 |

---

## 三、测试用例

### 测试1：词云库使用检查

**测试目的**: 验证图表12使用 `wordcloud` 库生成词云

**测试方法**:
```bash
# 检查 chart_12 源码中是否导入 wordcloud 库
grep -n "from wordcloud import\|import wordcloud" charts/chart_12_*.py
```

**验收条件**: 
- [ ] chart_12_*.py 文件存在
- [ ] 导入 wordcloud 库
- [ ] 调用 WordCloud 类生成图表

**预期输出**:
```
from wordcloud import WordCloud  # 或类似导入
w = WordCloud(...)
```

---

### 测试2：数据加载器验证

**测试目的**: 验证使用 `mda_loader.py` 加载模块6数据

**测试方法**:
```bash
# 检查图表源码是否导入 mda_loader
grep -n "from mda_loader\|import mda_loader" charts/chart_1{2,3,4}_*.py

# 检查 mda_loader.py 是否存在
ls -la mda_loader.py
```

**验收条件**:
- [ ] mda_loader.py 存在
- [ ] 图表12-14 导入并使用 mda_loader

---

### 测试3：PNG文件验收

**测试目的**: 验证3张PNG文件存在且符合规范

**测试方法**:
```bash
# 检查输出文件
ls -la output/*_chart12_*.png
ls -la output/*_chart13_*.png
ls -la output/*_chart14_*.png

# 验证文件名格式
# 格式: {stock_code}_chart{12,13,14}_{chart_name}.png
```

**验收条件**:
- [ ] 3张PNG文件均存在
- [ ] 文件名符合规范 `{股票代码}_chart12_*.png`
- [ ] 文件大小 > 10KB

---

### 测试4：分辨率验证

**测试目的**: 验证PNG文件分辨率≥150dpi

**测试方法**:
```python
# 使用PIL检查分辨率
from PIL import Image
img = Image.open('output/000001_chart12_wordcloud.png')
print(f"DPI: {img.info.get('dpi', 'N/A')}")
```

**验收条件**:
- [ ] PNG分辨率≥150dpi（或使用高分辨率生成）

---

### 测试5：中文标签无乱码

**测试目的**: 验证图表中文显示正常

**测试方法**:
```bash
# 检查 chart_factory.py 字体配置
grep -A10 "FONT_FALLBACK_CHAIN" chart_factory.py
```

**验收条件**:
- [ ] 字体fallback链包含Linux系统字体（Noto Sans CJK等）
- [ ] 图表中文标签显示正确

---

### 测试6：批量生成性能测试

**测试目的**: 验证3张MD&A图表生成时间≤30秒

**测试方法**:
```bash
# 运行生成测试（如果有测试脚本）
python3 test_phase4_charts.py
```

**验收条件**:
- [ ] 3张图表生成总耗时 < 30秒

---

## 四、测试数据准备

### 4.1 测试用股票代码

建议使用已获取MD&A数据的股票进行测试：
- `000001` - 平安银行
- `000858` - 五粮液
- `600036` - 招商银行

### 4.2 模块6数据准备

确保模块6已生成以下数据字段：
- `strategic_commitments` - 战略承诺列表
- `key_strategic_themes` - 关键战略主题
- `risk_factors` - 风险因素列表

---

## 五、验收清单

| 序号 | 验收项 | 状态 | 备注 |
|------|--------|------|------|
| 1 | 图表12 Python文件存在 | ☐ | chart_12_mda_wordcloud.py |
| 2 | 图表13 Python文件存在 | ☐ | chart_13_risk_timeline.py |
| 3 | 图表14 Python文件存在 | ☐ | chart_14_industry_radar.py |
| 4 | 使用 wordcloud 库生成词云 | ☐ | 图表12验证 |
| 5 | 使用 mda_loader.py 加载数据 | ☐ | 图表12-14验证 |
| 6 | PNG文件分辨率≥150dpi | ☐ | 3张图表验证 |
| 7 | 文件名规范 | ☐ | `{股票代码}_chart{NN}_{名称}.png` |
| 8 | 中文标签无乱码 | ☐ | 字体配置验证 |
| 9 | 批量生成时间≤30秒 | ☐ | 性能测试 |
| 10 | 文件大小>10KB | ☐ | 3张图表验证 |

---

## 六、待补充项（如未完成）

根据当前调研，以下文件/功能可能需要执行者补充：

| 待补充项 | 说明 |
|----------|------|
| `charts/chart_12_mda_wordcloud.py` | 词云图表实现 |
| `charts/chart_13_risk_timeline.py` | 风险时间线图表实现 |
| `charts/chart_14_industry_radar.py` | 行业雷达图实现 |
| `output/000001_chart12_*.png` | 词云PNG输出 |
| `output/000001_chart13_*.png` | 时间线PNG输出 |
| `output/000001_chart14_*.png` | 雷达图PNG输出 |

---

## 七、预期输出文件

Phase 4 验收通过后，应产生以下文件：

```
module5_charts/
├── charts/
│   ├── chart_12_mda_wordcloud.py      # 词云生成器
│   ├── chart_13_risk_timeline.py      # 风险时间线生成器
│   └── chart_14_industry_radar.py      # 行业雷达图生成器
├── output/
│   ├── 000001_chart12_mda_wordcloud.png  # 词云PNG
│   ├── 000001_chart13_risk_timeline.png  # 时间线PNG
│   └── 000001_chart14_industry_radar.png # 雷达图PNG
└── test_phase4_charts.py              # 验收测试脚本（如有）
```

---

**验收方案结束**

---

**签署信息**:
| 角色 | 姓名 | 日期 | 签署 |
|------|------|------|------|
| 测试工程师 | 测试专家 | 2026-04-06 | ⏳ |
| 评估审批 | - | 待定 | - |