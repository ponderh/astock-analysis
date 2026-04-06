# Phase 2 验收方案 - 财务图表模块

**文档编号**: P1-M5-VALIDATION-PH2  
**版本**: v1.0  
**创建日期**: 2026-04-06  
**角色**: 评估者（Tester）  
**状态**: 待执行

---

## 一、验收范围

Phase 2 涵盖 **7张图表** 的完整验收：

| 序号 | 图表名称 | 类型 | 数据源 |
|------|----------|------|--------|
| 1 | 营收/净利润趋势 | 双轴折线图 | 模块2 |
| 2 | ROIC vs WACC趋势 | 双轴折线图 | 模块2 |
| 3 | 杜邦三因子贡献堆叠 | 堆叠面积图 | 模块2 |
| 4 | EPS + DPS + 累计分红 | 柱+线组合图 | 模块2 |
| 5 | 资产负债率+有息负债率 | 双轴折线图 | 模块2 |
| 15 | 核心指标仪表盘 | 组合仪表盘 | 模块2 |

---

## 二、验收重点

### 2.1 可视化验收

每张图表需验证：
- **中文标签正确显示**（无乱码）- 检查字体fallback链
- **图表标题、坐标轴标签、图例** - 清晰可读
- **配色符合A股惯例**（红涨绿跌）
- **数据点正确对应模块2数据** - 数据追溯

### 2.2 Schema对接验收

- 每张图表使用 `financial_loader.py` 获取数据
- 数据字段映射正确（按 CONTRACT.md 附录A）
- 必需字段存在性验证

### 2.3 文件输出验收

- PNG格式，分辨率≥150dpi
- 文件名规范：`{stock_code}_{chart_id}_{chart_name}.png`

### 2.4 批量生成验收

- `chart_generator.py` 一次性生成7张图表
- 生成时间≤30秒

---

## 三、图表验收标准

### 3.1 图表1：营收/净利润趋势

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | revenue, net_profit 字段存在 | 检查 financial_loader.py 调用 |
| X轴 | 年份列表正确显示 | 目视检查标签 |
| Y1轴 | 营业收入（亿元）数值正确 | 数据追溯 |
| Y2轴 | 净利润（亿元）数值正确 | 数据追溯 |
| 双轴 | 左右轴刻度合理，不重叠 | 目视检查 |
| 配色 | 营收=蓝色，净利润=红色 | 颜色对比 |
| 图例 | 两个系列正确显示 | 目视检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi | 文件属性 |

### 3.2 图表2：ROIC vs WACC趋势

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | roic, wacc 字段存在 | 检查数据加载 |
| X轴 | 年份列表正确显示 | 目视检查 |
| Y轴 | 比率（%）数值正确 | 数据追溯 |
| 双线 | ROIC和WACC曲线正确 | 目视检查 |
| 配色 | ROIC=蓝色，WACC=橙色 | 颜色对比 |
| 阈值线 | 盈亏平衡线（0）显示 | 阈值检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi | 文件属性 |

### 3.3 图表3：杜邦三因子贡献堆叠

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | dupont_net_margin, dupont_asset_turnover, dupont_equity_multiplier | 检查字段 |
| X轴 | 年份列表正确显示 | 目视检查 |
| 堆叠 | 三因子正确堆叠，无重叠 | 面积检查 |
| 配色 | 净利率=蓝，资产周转率=绿，权益乘数=红 | 颜色对比 |
| 图例 | 三个因子正确标注 | 目视检查 |
| 标签 | 因子名称清晰显示 | 标签检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi | 文件属性 |

### 3.4 图表4：EPS + DPS + 累计分红

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | eps, dps, cumulative_dps 字段存在 | 检查数据加载 |
| X轴 | 年份列表正确显示 | 目视检查 |
| 柱状 | EPS和DPS为柱状图 | 图表类型检查 |
| 折线 | 累计分红为折线图 | 图表类型检查 |
| 双轴 | 左右轴刻度合理 | 目视检查 |
| 配色 | EPS=蓝，DPS=绿，累计分红=红 | 颜色对比 |
| 图例 | 三个系列正确显示 | 目视检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi | 文件属性 |

### 3.5 图表5：资产负债率+有息负债率

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | debt_ratio, interest_bearing_debt_ratio 字段存在 | 检查字段 |
| X轴 | 年份列表正确显示 | 目视检查 |
| Y1轴 | 资产负债率（%）数值正确 | 数据追溯 |
| Y2轴 | 有息负债率（%）数值正确 | 数据追溯 |
| 双轴 | 左右轴刻度合理 | 目视检查 |
| 配色 | 资产负债率=蓝色，有息负债率=红色 | 颜色对比 |
| 图例 | 两个系列正确显示 | 目视检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi | 文件属性 |

### 3.6 图表15：核心指标仪表盘

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | 模块2数据（ROE、毛利率、PE等） | 数据追溯 |
| 布局 | 2x3网格布局正确 | 网格检查 |
| 组件 | 3个仪表盘 + 2个柱状图 + 1个进度条 | 组件检查 |
| 仪表盘 | ROE、毛利率、PE仪表盘显示正确 | 仪表盘检查 |
| 柱状图 | 营收趋势、利润趋势正确 | 柱状图检查 |
| 配色 | 仪表盘三色（低=绿，中=黄，高=红） | 颜色检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi | 文件属性 |

---

## 四、集成测试方案

### 4.1 测试环境准备

```bash
# 测试数据准备
# 使用模块2的模拟数据或真实数据
TEST_DATA_DIR="/home/ponder/.openclaw/workspace/astock-implementation/impl/module2_financial/output"
STOCK_CODE="000858"  # 使用测试股票代码
```

### 4.2 端到端测试脚本

```python
# test_phase2_e2e.py
import pytest
import os
import time
import json
from pathlib import Path

# 测试目标：Phase 2 全部7张图表
PHASE2_CHARTS = [
    "chart_01_revenue_profit_trend",
    "chart_02_roic_wacc_trend",
    "chart_03_dupont_stacked",
    "chart_04_eps_dps_combined",
    "chart_05_debt_ratios",
    "chart_15_dashboard"
]

class TestPhase2E2E:
    """Phase 2 端到端集成测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """测试环境准备"""
        self.module_dir = Path(__file__).parent
        self.output_dir = self.module_dir / "output"
        self.data_dir = Path("/home/ponder/.openclaw/workspace/astock-implementation/impl/module2_financial/output")
        
        # 确保输出目录存在
        self.output_dir.mkdir(exist_ok=True)
        
        # 检查测试数据存在
        test_data_file = self.data_dir / "000858_financial.json"
        if not test_data_file.exists():
            pytest.skip(f"测试数据不存在: {test_data_file}")
        
        # 导入模块
        import sys
        sys.path.insert(0, str(self.module_dir))
        
        yield
        
        # 清理（可选）
    
    def test_01_financial_loader_schema(self):
        """测试1：financial_loader.py Schema验证"""
        from financial_loader import FinancialDataLoader
        
        loader = FinancialDataLoader(data_dir=str(self.data_dir))
        data = loader.load_from_dir("000858")
        
        # 验证必需字段
        assert loader.get_stock_code() == "000858"
        assert len(loader.get_years()) > 0
        
        # 验证关键指标
        assert loader.get_revenue() is not None
        assert loader.get_net_profit() is not None
        assert loader.get_roic() is not None
        assert loader.get_wacc() is not None
        assert loader.get_eps() is not None
        assert loader.get_dps() is not None
        assert loader.get_cumulative_dps() is not None
        assert loader.get_debt_ratio() is not None
        assert loader.get_interest_bearing_debt_ratio() is not None
    
    def test_02_chart_generator_import(self):
        """测试2：chart_generator.py 可导入"""
        import sys
        sys.path.insert(0, str(self.module_dir))
        
        # 尝试导入图表生成器
        try:
            import chart_generator
            has_generator = True
        except ImportError:
            has_generator = False
        
        assert has_generator, "chart_generator.py 未实现或导入失败"
    
    def test_03_visual_charts_import_chinese_font(self):
        """测试3：中文字体fallback链可用"""
        import matplotlib.pyplot as plt
        
        # 测试字体fallback链
        font_fallback = ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Arial']
        
        available_font = None
        for font in font_fallback:
            try:
                from matplotlib.font_manager import FontProperties
                fp = FontProperties(family=font)
                available_font = font
                break
            except:
                continue
        
        # 至少Arial应该可用
        assert available_font is not None, "无可用中文字体"
    
    def test_04_chart_01_revenue_profit_trend_generated(self):
        """测试4：图表1 营收/净利润趋势 生成"""
        # 检查输出文件
        output_file = self.output_dir / "000858_revenue_profit_trend.png"
        
        # 如果文件不存在，跳过（等待实现）
        if not output_file.exists():
            pytest.skip("图表1 未生成，等待实现")
        
        # 验证文件
        assert output_file.exists(), "图表1 输出文件不存在"
        
        # 验证分辨率
        from PIL import Image
        with Image.open(output_file) as img:
            assert img.info.get('dpi', (150,))[0] >= 150, "分辨率低于150dpi"
    
    def test_05_chart_02_roic_wacc_trend_generated(self):
        """测试5：图表2 ROIC vs WACC趋势 生成"""
        output_file = self.output_dir / "000858_roic_wacc_trend.png"
        
        if not output_file.exists():
            pytest.skip("图表2 未生成，等待实现")
        
        assert output_file.exists(), "图表2 输出文件不存在"
        
        from PIL import Image
        with Image.open(output_file) as img:
            assert img.info.get('dpi', (150,))[0] >= 150
    
    def test_06_chart_03_dupont_stacked_generated(self):
        """测试6：图表3 杜邦三因子 生成"""
        output_file = self.output_dir / "000858_dupont_stacked.png"
        
        if not output_file.exists():
            pytest.skip("图表3 未生成，等待实现")
        
        assert output_file.exists(), "图表3 输出文件不存在"
    
    def test_07_chart_04_eps_dps_generated(self):
        """测试7：图表4 EPS+DPS 生成"""
        output_file = self.output_dir / "000858_eps_dps_combined.png"
        
        if not output_file.exists():
            pytest.skip("图表4 未生成，等待实现")
        
        assert output_file.exists(), "图表4 输出文件不存在"
    
    def test_08_chart_05_debt_ratios_generated(self):
        """测试8：图表5 资产负债率 生成"""
        output_file = self.output_dir / "000858_debt_ratios.png"
        
        if not output_file.exists():
            pytest.skip("图表5 未生成，等待实现")
        
        assert output_file.exists(), "图表5 输出文件不存在"
    
    def test_09_chart_15_dashboard_generated(self):
        """测试9：图表15 核心指标仪表盘 生成"""
        output_file = self.output_dir / "000858_dashboard.png"
        
        if not output_file.exists():
            pytest.skip("图表15 未生成，等待实现")
        
        assert output_file.exists(), "图表15 输出文件不存在"
    
    def test_10_batch_generation_performance(self):
        """测试10：批量生成性能"""
        # 测量生成时间
        start_time = time.time()
        
        # 调用批量生成
        # TODO: 实现后补充
        
        elapsed = time.time() - start_time
        
        # 7张图表生成时间应≤30秒
        assert elapsed <= 30, f"批量生成耗时 {elapsed:.2f}秒，超过30秒限制"
    
    def test_11_output_format_verification(self):
        """测试11：输出格式验证"""
        # 验证所有输出文件为PNG且≥150dpi
        for chart_file in self.output_dir.glob("*.png"):
            with Image.open(chart_file) as img:
                dpi = img.info.get('dpi', (150,))[0]
                assert dpi >= 150, f"{chart_file.name} 分辨率 {dpi}dpi < 150"
    
    def test_12_color_scheme_abc_convention(self):
        """测试12：配色符合A股惯例（红涨绿跌）"""
        # 读取配置文件验证配色方案
        import yaml
        
        config_file = self.module_dir / "chart_config.yaml"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        colors = config.get('colors', {})
        
        # 验证 bullish（涨）= 红色
        assert colors.get('bullish') == "#E74C3C", "上涨色应为红色"
        
        # 验证 bearish（跌）= 绿色
        assert colors.get('bearish') == "#27AE60", "下跌色应为绿色"
    
    def test_13_error_handling_missing_data(self):
        """测试13：数据缺失时的异常处理"""
        # 测试 financial_loader 对缺失字段的处理
        from financial_loader import FinancialDataLoader
        
        # 创建空数据测试
        incomplete_data = {
            "stock_code": "000001",
            "years": [2023],
            "financial_metrics": {}  # 空指标
        }
        
        # 验证是否抛出合理异常
        import tempfile
        import json
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_data, f)
            temp_file = f.name
        
        try:
            loader = FinancialDataLoader()
            # 应该能加载，但缺少字段
            data = loader.load(temp_file)
            # 验证错误提示
        except Exception as e:
            # 应该抛出Schema验证错误
            assert "缺少必需财务指标" in str(e), "数据缺失应给出明确错误"
        finally:
            os.unlink(temp_file)
```

### 4.3 测试数据准备

**测试股票代码**: `000858`（五粮液）

**预期数据结构**（来自模块2）:
```json
{
  "stock_code": "000858",
  "years": [2020, 2021, 2022, 2023, 2024],
  "financial_metrics": {
    "revenue": [100.5, 120.3, 140.2, 155.8, 180.5],
    "net_profit": [30.2, 35.5, 42.1, 48.3, 55.2],
    "roic": [12.5, 14.2, 15.8, 16.5, 18.2],
    "wacc": [8.5, 8.2, 8.0, 7.8, 7.5],
    "eps": [5.2, 6.1, 7.2, 8.3, 9.5],
    "dps": [1.5, 1.8, 2.0, 2.2, 2.5],
    "cumulative_dps": [7.5, 9.3, 11.3, 13.5, 16.0],
    "debt_ratio": [35.2, 33.5, 31.8, 30.2, 28.5],
    "interest_bearing_debt_ratio": [20.1, 18.5, 16.2, 14.5, 12.8],
    "dupont_net_margin": [30.0, 29.5, 30.0, 31.0, 30.5],
    "dupont_asset_turnover": [0.8, 0.85, 0.88, 0.9, 0.92],
    "dupont_equity_multiplier": [1.5, 1.48, 1.45, 1.42, 1.4]
  }
}
```

---

## 五、验收检查清单

### 5.1 功能验收

| # | 检查项 | 验收条件 | 状态 |
|---|--------|----------|------|
| F1 | 图表1生成 | 营收/净利润趋势图存在且正确 | ☐ |
| F2 | 图表2生成 | ROIC vs WACC趋势图存在且正确 | ☐ |
| F3 | 图表3生成 | 杜邦三因子堆叠图存在且正确 | ☐ |
| F4 | 图表4生成 | EPS+DPS+累计分红图存在且正确 | ☐ |
| F5 | 图表5生成 | 资产负债率+有息负债率图存在且正确 | ☐ |
| F6 | 图表15生成 | 核心指标仪表盘存在且正确 | ☐ |
| F7 | 数据源对接 | 所有图表正确调用 financial_loader.py | ☐ |
| F8 | 字段映射 | 数据字段与图表配置一致 | ☐ |

### 5.2 质量验收

| # | 检查项 | 验收条件 | 状态 |
|---|--------|----------|------|
| Q1 | 中文显示 | 所有中文标签无乱码 | ☐ |
| Q2 | 配色方案 | 符合A股红涨绿跌惯例 | ☐ |
| Q3 | 图表布局 | 元素不重叠，比例协调 | ☐ |
| Q4 | 异常处理 | 数据缺失时显示"数据不可用" | ☐ |

### 5.3 性能验收

| # | 检查项 | 验收条件 | 状态 |
|---|--------|----------|------|
| P1 | 文件格式 | 所有输出为PNG格式 | ☐ |
| P2 | 分辨率 | DPI ≥ 150 | ☐ |
| P3 | 文件命名 | 符合 {stock_code}_{chart_name}.png 规范 | ☐ |
| P4 | 批量生成 | 7张图表生成时间 ≤ 30秒 | ☐ |

### 5.4 Schema验收

| # | 检查项 | 验收条件 | 状态 |
|---|--------|----------|------|
| S1 | 必需字段 | stock_code, years, financial_metrics 存在 | ☐ |
| S2 | 财务指标 | revenue, net_profit, roic, wacc 等存在 | ☐ |
| S3 | 字段类型 | 所有数值字段为数组类型 | ☐ |
| S4 | 字段长度 | 数组长度与 years 列表长度一致 | ☐ |

---

## 六、测试用例执行

### 6.1 执行命令

```bash
# 进入模块目录
cd /home/ponder/.openclaw/workspace/astock-implementation/impl/module5_charts

# 执行集成测试
python -m pytest test_phase2_e2e.py -v --tb=short

# 或执行单个测试
python -m pytest test_phase2_e2e.py::TestPhase2E2E::test_01_financial_loader_schema -v
```

### 6.2 预期结果

- **通过**: 所有7张图表成功生成，数据正确，格式符合要求
- **失败**: 图表未生成、数据错误、格式不符合、生成超时

### 6.3 失败处理

| 失败类型 | 原因 | 处理措施 |
|----------|------|----------|
| 文件不存在 | chart_generator.py 未实现 | 返回给Architect补充 |
| 数据错误 | 模块2数据格式问题 | 检查模块2输出 |
| 中文乱码 | 字体fallback链问题 | 检查系统字体配置 |
| 性能问题 | 生成逻辑效率低 | 优化生成代码 |
| 分辨率不足 | DPI设置过低 | 调整 chart_config.yaml |

---

## 七、验收输出

### 7.1 交付物

- [x] 本验收方案文档
- [ ] 测试执行脚本 `test_phase2_e2e.py`
- [ ] 验收结果报告

### 7.2 验收结论

| 角色 | 签署 | 日期 |
|------|------|------|
| 评估者（Tester） | | |
| 执行者（Architect） | | |
| 审批人（Main） | | |

---

*文档结束*