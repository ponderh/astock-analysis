# Phase 1 验收方案

**文档编号**: P1-M5-VALIDATION  
**版本**: v1.0  
**创建日期**: 2026-04-06  
**角色**: 评估者=Tester  
**状态**: 待执行

---

## 一、验收范围

Phase 1 交付物：

| 交付物 | 文件 | 说明 |
|--------|------|------|
| M5-P1-D1 | `financial_loader.py` | 模块2数据加载器 |
| M5-P1-D2 | `mda_loader.py` | 模块6数据加载器 |
| M5-P1-D3 | `chart_config.yaml` | 15张图表完整配置 |
| M5-P1-D4 | `README.md` | 使用文档 |

---

## 二、验收检查清单

### 2.1 FinancialDataLoader 验收 (financial_loader.py)

| 序号 | 检查项 | 验收标准 | 测试方法 |
|------|--------|----------|----------|
| F1.1 | 文件存在 | `financial_loader.py` 存在于 module5_charts 目录 | 文件检查 |
| F1.2 | 模块导入 | 导入时不抛异常 | Python import 测试 |
| F1.3 | 类/函数定义 | 包含 `FinancialDataLoader` 类或等价加载函数 | 代码检查 |
| F1.4 | 模块2对接 | 正确导入/调用模块2的API (get_financial_history/get_derived_metrics) | 代码检查 |
| F1.5 | JSON输出格式 | `load()` 方法返回符合 CONTRACT 附录A的JSON Schema | Schema验证 |
| F1.6 | 必填字段 | stock_code, years, financial_metrics.revenue, financial_metrics.net_profit 等必填 | 数据注入 |
| F1.7 | 字段类型 | years为整数数组, financial_metrics各项为数字数组 | 类型检查 |
| F1.8 | Schema校验 | 注入错误格式数据时抛出 ValidationError 或等效异常 | 异常测试 |
| F1.9 | 关键字段缺失处理 | 缺少必填字段时抛出明确错误 | 缺失测试 |
| F1.10 | 空数据处理 | 空DataFrame输入时有合理处理 (返回空/默认值/抛异常) | 空输入测试 |

### 2.2 MD&ADataLoader 验收 (mda_loader.py)

| 序号 | 检查项 | 验收标准 | 测试方法 |
|------|--------|----------|----------|
| M1.1 | 文件存在 | `mda_loader.py` 存在于 module5_charts 目录 | 文件检查 |
| M1.2 | 模块导入 | 导入时不抛异常 | Python import 测试 |
| M1.3 | 类/函数定义 | 包含 `MD&ADataLoader` 类或等价加载函数 | 代码检查 |
| M1.4 | 模块6对接 | 正确导入/调用模块6的API (MDAResult) | 代码检查 |
| M1.5 | JSON输出格式 | `load()` 方法返回符合 CONTRACT 附录A的JSON Schema | Schema验证 |
| M1.6 | 必填字段 | stock_code, strategic_commitments, key_strategic_themes, risk_factors 必填 | 数据注入 |
| M1.7 | 字段类型 | strategic_commitments 为数组, 各元素为对象 | 类型检查 |
| M1.8 | Schema校验 | 注入错误格式数据时抛出 ValidationError 或等效异常 | 异常测试 |
| M1.9 | 嵌套字段验证 | commitment/time_horizon/quantitative_target 等子字段类型正确 | 嵌套检查 |
| M1.10 | 空MD&A处理 | 模块6返回None/空Result时有合理降级 | 空输入测试 |

### 2.3 ChartConfig.yaml 验收 (chart_config.yaml)

| 序号 | 检查项 | 验收标准 | 测试方法 |
|------|--------|----------|----------|
| C1.1 | 文件存在 | `chart_config.yaml` 存在于 module5_charts 目录 | 文件检查 |
| C1.2 | YAML格式 | 可用PyYAML正确解析，无语法错误 | PyYAML load测试 |
| C1.3 | 图表数量 | 包含 15 张图表配置 | 计数检查 |
| C1.4 | 图表类型 | 每张图有 chart_type 字段 | 类型检查 |
| C1.5 | 数据来源 | 每张图有 data_source 字段 (module2/module6) | 来源检查 |
| C1.6 | 字段映射 | 每张图有 data_fields 配置 (x/y轴字段) | 映射检查 |
| C1.7 | 财务图表(6张) | 图1-6对应 module2 数据 | 逐图检查 |
| C1.8 | 估值+季节图表(5张) | 图7-11对应 module2 数据 | 逐图检查 |
| C1.9 | MD&A图表(3张) | 图12-14对应 module6 数据 | 逐图检查 |
| C1.10 | 综合仪表盘 | 图15 同时引用 module2 和 module6 | 来���检查 |
| C1.11 | 配色方案 | 包含 color_scheme 配置 (红涨绿跌) | 配置检查 |
| C1.12 | 输出格式 | 包含 output_format (PNG/dpi) 配置 | 配置检查 |

### 2.4 README.md 验收

| 序号 | 检查项 | 验收标准 | 测试方法 |
|------|--------|----------|----------|
| R1.1 | 文件存在 | `README.md` 存在于 module5_charts 目录 | 文件检查 |
| R1.2 | 使用说明 | 包含模块化调用示例 (加载数据 → 生成图表) | 内容检查 |
| R1.3 | FinancialLoader | 包含 financial_loader.py 使用示例 | 内容检查 |
| R1.4 | MD&ALoader | 包含 mda_loader.py 使用示例 | 内容检查 |
| R1.5 | ChartConfig | 包含 chart_config.yaml 使用说明 | 内容检查 |
| R1.6 | 依赖说明 | 包含依赖库列表 (matplotlib, seaborn, pyyaml等) | 内容检查 |
| R1.7 | 数据格式 | 说明输入数据格式 (模块2/模块6输出) | 内容检查 |
| R1.8 | 输出说明 | 说明输出图表格式和位置 | 内容检查 |

---

## 三、测试用例设计

### 3.1 FinancialDataLoader 测试用例

```python
# TC-F1: 正常数据加载
def test_financial_loader_normal():
    """输入：模块2正常DataFrame → 输出：符合Schema的JSON"""
    loader = FinancialDataLoader()
    result = loader.load(test_df)  # test_df 为符合模块2格式的测试数据
    assert result['stock_code'] == '002014'
    assert 'revenue' in result['financial_metrics']
    assert 'net_profit' in result['financial_metrics']

# TC-F2: Schema校验 - 类型错误
def test_financial_loader_type_error():
    """输入：revenue为字符串而非数字 → 应抛出ValidationError"""
    loader = FinancialDataLoader()
    invalid_df = test_df.copy()
    invalid_df['revenue'] = 'abc'  # 类型错误
    try:
        loader.load(invalid_df)
        assert False, "应抛出 ValidationError"
    except (ValidationError, ValueError, TypeError):
        pass  # 预期异常

# TC-F3: Schema校验 - 缺少必填字段
def test_financial_loader_missing_field():
    """输入：缺少net_profit字段 → 应抛出ValidationError"""
    loader = FinancialDataLoader()
    invalid_df = test_df.drop(columns=['net_profit'])
    try:
        loader.load(invalid_df)
        assert False, "应抛出 ValidationError"
    except (ValidationError, ValueError, KeyError):
        pass  # 预期异常

# TC-F4: 空数据处理
def test_financial_loader_empty():
    """输入：空DataFrame → 应有合理处理"""
    loader = FinancialDataLoader()
    empty_df = pd.DataFrame()
    result = loader.load(empty_df)
    # 选项A: 返回包含空值的JSON
    # 选项B: 抛出明确异常
    # 选项C: 返回错误信息
    assert result is not None or isinstance(result, dict)
```

### 3.2 MD&ADataLoader 测试用例

```python
# TC-M1: 正常数据加载
def test_mda_loader_normal():
    """输入：正常MDAResult → 输出：符合Schema的JSON"""
    loader = MD&ADataLoader()
    result = loader.load(test_mda_result)
    assert result['stock_code'] == '002014'
    assert 'strategic_commitments' in result

# TC-M2: Schema校验 - 嵌套字段缺失
def test_mda_loader_nested_missing():
    """输入：strategic_commitments元素缺少commitment字段 → 应抛出ValidationError"""
    loader = MD&ADataLoader()
    invalid_data = {
        'stock_code': '002014',
        'strategic_commitments': [
            {'time_horizon': '2025', 'quantitative_target': '100亿'}  # 缺少commitment
        ]
    }
    try:
        loader.load(invalid_data)
        assert False, "应抛出 ValidationError"
    except (ValidationError, ValueError, KeyError):
        pass

# TC-M3: 类型校验 - 数组类型错误
def test_mda_loader_type_error():
    """输入：strategic_commitments为字符串而非数��� → 应抛出ValidationError"""
    loader = MD&ADataLoader()
    invalid_data = {
        'stock_code': '002014',
        'strategic_commitments': 'not an array'  # 类型错误
    }
    try:
        loader.load(invalid_data)
        assert False, "应抛出 ValidationError"
    except (ValidationError, ValueError, TypeError):
        pass

# TC-M4: 空MD&A处理
def test_mda_loader_empty():
    """输入：None → 应有合理降级"""
    loader = MD&ADataLoader()
    result = loader.load(None)
    # 应返回默认值或空结构，不应抛未处理异常
    assert result is not None or isinstance(result, dict)
```

### 3.3 ChartConfig.yaml 测试用例

```python
# TC-C1: YAML解析
def test_chart_config_parse():
    """chart_config.yaml应可正确解析"""
    with open('chart_config.yaml') as f:
        config = yaml.safe_load(f)
    assert config is not None

# TC-C2: 图表数量
def test_chart_config_count():
    """应包含15张图表"""
    with open('chart_config.yaml') as f:
        config = yaml.safe_load(f)
    assert len(config.get('charts', [])) == 15

# TC-C3: 数据来源覆盖
def test_chart_config_data_sources():
    """15张图的数据来源应覆盖module2和module6"""
    with open('chart_config.yaml') as f:
        config = yaml.safe_load(f
    sources = set(c.get('data_source') for c in config.get('charts', []))
    assert 'module2' in sources
    assert 'module6' in sources

# TC-C4: 必需字段
def test_chart_config_required_fields():
    """每张图应有chart_type和data_fields"""
    with open('chart_config.yaml') as f:
        config = yaml.safe_load(f)
    for chart in config.get('charts', []):
        assert 'chart_type' in chart, f"图 {chart.get('name')} 缺少 chart_type"
        assert 'data_fields' in chart, f"图 {chart.get('name')} 缺少 data_fields"
```

---

## 四、测试数据构造

### 4.1 模块2测试数据 (financial_loader.py)

```python
# 符合Schema的正确测试数据
TEST_FINANCIAL_DATA = {
    "stock_code": "002014",
    "years": [2020, 2021, 2022, 2023, 2024],
    "financial_metrics": {
        "revenue": [100.5, 120.3, 135.8, 150.2, 168.0],
        "net_profit": [15.2, 18.5, 22.1, 25.3, 28.9],
        "roe": [12.5, 14.2, 15.8, 16.5, 17.2],
        "roic": [10.2, 11.5, 12.8, 13.5, 14.2],
        "wacc": [8.5, 8.2, 8.0, 7.8, 7.5],
        "eps": [1.52, 1.85, 2.21, 2.53, 2.89],
        "dps": [0.5, 0.6, 0.7, 0.8, 0.9],
        "cfo": [18.5, 20.2, 25.8, 28.3, 32.1],
        "total_assets": [200.5, 220.3, 250.8, 280.2, 310.5],
        "net_assets": [120.5, 135.2, 150.8, 168.2, 185.5],
        "gross_margin": [28.5, 29.2, 30.5, 31.2, 32.0],
        "debt_ratio": [40.2, 38.5, 36.2, 35.8, 34.5],
        "interest_bearing_debt_ratio": [25.5, 24.2, 22.8, 21.5, 20.2],
        "pe": [15.2, 12.8, 11.5, 10.2, 9.5],
        "pb": [2.5, 2.2, 2.0, 1.8, 1.6],
        "ps": [3.2, 2.8, 2.5, 2.2, 2.0],
        "dupont_net_margin": [15.1, 15.4, 16.3, 16.8, 17.2],
        "dupont_asset_turnover": [0.5, 0.55, 0.54, 0.54, 0.54],
        "dupont_equity_multiplier": [1.65, 1.68, 1.67, 1.67, 1.67],
        "cumulative_dps": [2.5, 3.1, 3.8, 4.6, 5.5],
        "quarterly_revenue": [25.1, 28.2, 30.5, 35.2, 38.5, 40.2, 42.5, 45.8, 48.2, 50.5, 52.8, 55.2, 58.5, 60.2, 62.5, 65.8, 68.2, 70.5, 72.8, 75.2],
        "quarterly_profit": [3.2, 4.5, 5.2, 6.8, 7.5, 8.2, 8.8, 9.5, 10.2, 10.8, 11.2, 11.8, 12.5, 13.2, 13.8, 14.5, 15.2, 15.8, 16.2, 16.8]
    }
}

# 错误测试数据：类型错误
INVALID_FINANCIAL_TYPE = {
    "stock_code": "002014",
    "years": [2020, 2021, 2022],
    "financial_metrics": {
        "revenue": ["not_a_number", 120.3, 135.8],  # 类型错误
        "net_profit": [15.2, 18.5, 22.1]
    }
}

# 错误测试数据：缺少必填字段
INVALID_FINANCIAL_MISSING = {
    "stock_code": "002014",
    "years": [2020, 2021, 2022],
    "financial_metrics": {
        "revenue": [100.5, 120.3, 135.8]
        # 缺少 net_profit
    }
}
```

### 4.2 模块6测试数据 (mda_loader.py)

```python
# 符合Schema的正确测试数据
TEST_MDA_DATA = {
    "stock_code": "002014",
    "strategic_commitments": [
        {
            "commitment": "保持营收年复合增长率20%以上",
            "time_horizon": "2025",
            "quantitative_target": "2025年营收达到500亿"
        },
        {
            "commitment": "研发投入占比提升至15%",
            "time_horizon": "2026",
            "quantitative_target": "研发费用80亿"
        }
    ],
    "key_strategic_themes": [
        {
            "theme": "技术创新",
            "description": "加大AI和数字化投入"
        },
        {
            "theme": "全球化",
            "description": "拓展海外市场"
        }
    ],
    "risk_factors": [
        {
            "risk": "原材料价格波动",
            "mitigation": "锁价协议"
        },
        {
            "risk": "汇率波动",
            "mitigation": "外汇对冲"
        }
    ]
}

# 错误测试数据：嵌套字段缺失
INVALID_MDA_NESTED = {
    "stock_code": "002014",
    "strategic_commitments": [
        {
            "time_horizon": "2025"
            # 缺少 commitment 和 quantitative_target
        }
    ]
}

# 错误测试数据：类型错误
INVALID_MDA_TYPE = {
    "stock_code": "002014",
    "strategic_commitments": "not_an_array"  # 应为数组
}
```

---

## 五、验收执行步骤

### 步骤1：文件存在性检查
```bash
cd /home/ponder/.openclaw/workspace/astock-implementation/impl/module5_charts/
ls -la financial_loader.py mda_loader.py chart_config.yaml README.md
```

### 步骤2：Python模块导入测试
```bash
python3 -c "from financial_loader import FinancialDataLoader; print('OK')"
python3 -c "from mda_loader import MD&ADataLoader; print('OK')"
python3 -c "import yaml; print('OK')"
```

### 步骤3：数据加载测试
```python
# 见 3.1/3.2/3.3 测试用例
```

### 步骤4：Schema校验测试
```python
# 注入错误数据，验证异常抛出
```

### 步骤5：ChartConfig验证
```bash
python3 -c "import yaml; c=yaml.safe_load(open('chart_config.yaml')); print(len(c['charts']))"
```

---

## 六、验收通过标准

| 类别 | 通过条件 |
|------|----------|
| FinancialDataLoader | F1.1-F1.10 全部通过 |
| MD&ADataLoader | M1.1-M1.10 全部通过 |
| ChartConfig.yaml | C1.1-C1.12 全部通过 |
| README.md | R1.1-R1.8 全部通过 |

**Phase 1 整体通过**：4个交付物全部通过验收

---

## 七、后续阶段提醒

- Phase 2: chart_generator.py 和图表生成测试
- Phase 3: 15张图表逐图渲染验证
- Phase 4: 集成测试和性能测试

---

*验收方案编制：Tester | 审核：待 | 日期：2026-04-06*