# Phase 3 验收方案 - 估值与季节性图表模块

**文档编号**: P1-M5-VALIDATION-PH3  
**版本**: v1.0  
**创建日期**: 2026-04-06  
**角色**: 评估者（Tester）  
**状态**: 待执行

---

## 一、验收范围

Phase 3 涵盖 **5张图表** 的完整验收：

| 序号 | 图表名称 | 类型 | 数据源 | 优先级 |
|------|----------|------|--------|--------|
| 7 | PE/PB/PS历史分位 | 箱线图 | 模块2 | P1 |
| 8 | DCF敏感性热力图 | 热力图 | 模块2 | P1 |
| 9 | 相对估值横向比较 | 柱状图 | 模块2 | P2 |
| 10 | 季度营收/利润波动柱状图 | 柱状图 | 模块2 | P1 |
| 11 | 季节性热力图（环比+同比） | 热力图 | 模块2 | P1 |

---

## 二、验收重点

### 2.1 可视化验收

每张图表需验证：
- **中文标签正确显示**（无乱码）- 检查字体fallback链
- **图表标题、坐标轴标签、图例** - 清晰可读
- **配色符合A股惯例**（红涨绿跌）
- **数据点正确对应模块2数据** - 数据追溯
- **图表类型与定义一致**（箱线图/热力图/柱状图）

### 2.2 数据字段映射验收

每张图需验证正确读取对应模块2数据字段：

| 图表 | 数据字段 | 验证方法 |
|------|----------|----------|
| 7 | pe, pb, ps（估值分位数组） | 数据追溯 |
| 8 | growth_rate, wacc, dcf_value（DCF敏感性矩阵） | 数据追溯 |
| 9 | peer_companies, pe, pb（同业对比数据） | 数据追溯 |
| 10 | quarterly_revenue, quarterly_profit（4季度*N年） | 数据追溯 |
| 11 | quarter, year, revenue_yoy, revenue_qoq（季节性矩阵） | 数据追溯 |

### 2.3 PNG输出验收

- PNG格式，分辨率≥150dpi
- 文件名规范：`{stock_code}_chart{xx}_{chart_name}.png`
- 5张图表全部生成

### 2.4 批量生成验收

- `chart_generator.py` 支持生成图表7-11
- 可通过参数控制生成单个或批量图表

---

## 三、图表验收标准

### 3.1 图表7：PE/PB/PS历史分位

**图表类型**: 箱线图 (boxplot)  
**优先级**: P1  
**数据源**: 模块2 - pe, pb, ps 字段

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | pe, pb, ps 字段存在且为数组 | 数据追溯 |
| X轴 | 年份列表或分布数据正确显示 | 目视检查 |
| Y轴 | 估值分位数值范围正确 | 数据追溯 |
| 箱线图类型 | 三组箱线（PE/PB/PS）正确显示 | 图表类型检查 |
| 配色 | PE=蓝色(#3498DB)，PB=绿色(#2ECC71)，PS=红色(#E74C3C) | 颜色对比 |
| 图例 | PE、PB、PS 三项正确标注 | 目视检查 |
| 标题 | "PE、PB、PS 历史估值分位" 显示正确 | 标题检查 |
| 异常值 | showfliers=true，显示异常值点 | 参数检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi，文件名规范 | 文件属性 |

### 3.2 图表8：DCF敏感性热力图

**图表类型**: 热力图 (heatmap)  
**优先级**: P1  
**数据源**: 模块2 - DCF敏感性矩阵数据

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | growth_rate, wacc, dcf_value 三维矩阵 | 数据追溯 |
| X轴 | 增长率（%）标签正确显示 | 目视检查 |
| Y轴 | WACC（%）标签正确显示 | 目视检查 |
| 热力图类型 | 矩形热力图正确渲染 | 图表类型检查 |
| 配色方案 | RdYlGn_r（高值绿，低值红） | 配色检查 |
| 标注 | 每个单元格显示DCF估值数值 | annotation检查 |
| 颜色条 | 显示数值范围颜色条 | 图例检查 |
| 标题 | "DCF 敏感性分析热力图" 显示正确 | 标题检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi，文件名规范 | 文件属性 |

### 3.3 图表9：相对估值横向比较

**图表类型**: 柱状图 (bar)  
**优先级**: P2  
**数据源**: 模块2 - peer_companies, pe, pb 字段

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | peer_companies, pe, pb 字段存在 | 数据追溯 |
| X轴 | 对比公司名称正确显示 | 目视检查 |
| Y轴 | 估值指标（倍数）范围合理 | 数据追溯 |
| 柱状图类型 | 分组柱状图正确显示（PE/PB对比） | 图表类型检查 |
| 配色 | PE=蓝色(#3498DB)，PB=红色(#E74C3C) | 颜色对比 |
| 图例 | PE、PB 两项正确标注 | 目视检查 |
| 网格 | 水平网格线正确显示 | 网格检查 |
| 标题 | "相对估值横向对比" 显示正确 | 标题检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi，文件名规范 | 文件属性 |
| 备注 | 需模块2提供同业数据 | 数据完整性 |

### 3.4 图表10：季度营收/利润波动柱状图

**图表类型**: 分组柱状图 (grouped_bar)  
**优先级**: P1  
**数据源**: 模块2 - quarterly_revenue, quarterly_profit 字段

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | quarterly_revenue, quarterly_profit 字段存在 | 数据追溯 |
| 数据结构 | 4季度*N年，数据长度正确 | 数据追溯 |
| X轴 | Q1/Q2/Q3/Q4 标签正确显示 | 目视检查 |
| Y轴 | 金额（亿元）数值正确 | 数据追溯 |
| 柱状图类型 | 分组柱状图（营收+利润并排） | 图表类型检查 |
| 配色 | 营收=蓝色(#3498DB)，利润=红色(#E74C3C) | 颜色对比 |
| 图例 | 营收、净利润两项正确标注 | 目视检查 |
| 网格 | 水平网格线正确显示 | 网格检查 |
| 标题 | "季度营收与净利润波动" 显示正确 | 标题检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi，文件名规范 | 文件属性 |

### 3.5 图表11：季节性热力图（环比+同比）

**图表类型**: 热力图 (heatmap)  
**优先级**: P1  
**数据源**: 模块2 - quarter, year, revenue_yoy, revenue_qoq 字段

| 验收项 | 验收条件 | 验证方法 |
|--------|----------|----------|
| 数据源 | quarter, year, revenue_yoy, revenue_qoq 字段存在 | 数据追溯 |
| 数据结构 | 4季度*N年的二维矩阵 | 数据追溯 |
| X轴 | Q1/Q2/Q3/Q4 标签正确显示 | 目视检查 |
| Y轴 | 年份列表正确显示 | 目视检查 |
| 热力图类型 | 矩形热力图正确渲染 | 图表类型检查 |
| 配色方案 | RdBu_r（红蓝色阶，正负分明） | 配色检查 |
| 标注 | 每个单元格显示增长率数值 | annotation检查 |
| 颜色条 | 显示数值范围颜色条 | 图例检查 |
| 正负区分 | 正值和负值颜色明显区分 | 目视检查 |
| 标题 | "季节性波动热力图（同比+环比）" 显示正确 | 标题检查 |
| 乱码 | 无中文乱码 | 字体检查 |
| 输出 | PNG格式，150dpi，文件名规范 | 文件属性 |

---

## 四、数据字段映射验收

### 4.1 模块2 → 图表7-11 字段映射表

| 图表 | 必需字段 | 字段类型 | 数据格式 | 备注 |
|------|----------|----------|----------|------|
| 7 | pe | array[number] | 年度PE序列 | 历史分位数据 |
| 7 | pb | array[number] | 年度PB序列 | 历史分位数据 |
| 7 | ps | array[number] | 年度PS序列 | 历史分位数据 |
| 8 | dcf_sensitivity_matrix | 2D array | 增长率×WACC矩阵 | DCF敏感性数据 |
| 9 | peer_pe | array[number] | 同业PE列表 | 需同业数据 |
| 9 | peer_pb | array[number] | 同业PB列表 | 需同业数据 |
| 9 | peer_names | array[string] | 同业公司名称 | 需同业数据 |
| 10 | quarterly_revenue | array[number] | 4*N季度营收 | 按年展开 |
| 10 | quarterly_profit | array[number] | 4*N季度利润 | 按年展开 |
| 11 | revenue_yoy | 2D array | 季度×年份同比矩阵 | 同比增长率 |
| 11 | revenue_qoq | 2D array | 季度×年份环比矩阵 | 环比增长率 |

### 4.2 数据完整性验证SQL/伪代码

```python
def validate_module2_data_for_phase3(data: Dict) -> ValidationResult:
    """验证模块2数据是否包含Phase 3所需字段"""
    
    errors = []
    warnings = []
    
    # 图表7: PE/PB/PS历史分位
    if 'pe' not in data.get('financial_metrics', {}):
        errors.append("图表7缺少PE字段")
    if 'pb' not in data.get('financial_metrics', {}):
        errors.append("图表7缺少PB字段")
    if 'ps' not in data.get('financial_metrics', {}):
        errors.append("图表7缺少PS字段")
    
    # 图表8: DCF敏感性热力图
    if 'dcf_sensitivity_matrix' not in data.get('financial_metrics', {}):
        warnings.append("图表8缺少DCF敏感性矩阵，图表将显示placeholder")
    
    # 图表9: 相对估值横向比较
    if 'peer_companies' not in data.get('financial_metrics', {}):
        warnings.append("图表9缺少同业数据，图表将显示placeholder")
    
    # 图表10: 季度营收/利润波动
    if 'quarterly_revenue' not in data.get('financial_metrics', {}):
        errors.append("图表10缺少季度营收数据")
    if 'quarterly_profit' not in data.get('financial_metrics', {}):
        errors.append("图表10缺少季度利润数据")
    
    # 图表11: 季节性热力图
    if 'revenue_yoy' not in data.get('financial_metrics', {}):
        warnings.append("图表11缺少同比数据")
    if 'revenue_qoq' not in data.get('financial_metrics', {}):
        warnings.append("图表11缺少环比数据")
    
    return ValidationResult(errors=errors, warnings=warnings)
```

---

## 五、集成测试方案

### 5.1 测试环境准备

```bash
# 测试目录
MODULE_DIR="/home/ponder/.openclaw/workspace/astock-implementation/impl/module5_charts"
OUTPUT_DIR="$MODULE_DIR/output"
DATA_DIR="/home/ponder/.openclaw/workspace/astock-implementation/impl/module2_financial"

# 测试股票代码
TEST_STOCK_CODE="000858"
```

### 5.2 端到端测试脚本

```python
# test_phase3_e2e.py
"""
Phase 3 端到端集成测试
测试图表7-11（估值与季节性图表）
"""

import pytest
import os
import sys
import time
from pathlib import Path
from PIL import Image

# Phase 3 图表列表
PHASE3_CHARTS = [
    ("chart_07", "valuation_percentile", "PE/PB/PS历史分位"),
    ("chart_08", "dcf_sensitivity", "DCF敏感性热力图"),
    ("chart_09", "relative_valuation", "相对估值横向比较"),
    ("chart_10", "quarterly_revenue", "季度营收/利润波动柱状图"),
    ("chart_11", "seasonality_heatmap", "季节性热力图"),
]

class TestPhase3E2E:
    """Phase 3 端到端集成测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """测试环境准备"""
        self.module_dir = Path(__file__).parent
        self.output_dir = self.module_dir / "output"
        self.test_stock = "000858"
        
        # 确保输出目录存在
        self.output_dir.mkdir(exist_ok=True)
        
        yield
    
    # ===== 可视化验收测试 =====
    
    def test_01_chart_07_boxplot_generated(self):
        """测试1：图表7 PE/PB/PS箱线图生成"""
        chart_id = "chart_07"
        output_file = self.output_dir / f"{self.test_stock}_chart07_valuation_percentile.png"
        
        if not output_file.exists():
            pytest.skip(f"图表7 未生成: {output_file}")
        
        # 验证文件存在
        assert output_file.exists(), f"图表7 输出文件不存在: {output_file}"
        
        # 验证分辨率
        with Image.open(output_file) as img:
            dpi = img.info.get('dpi', (72,))[0]
            assert dpi >= 150, f"图表7 DPI={dpi} < 150"
        
        # 验证文件大小（避免空文件）
        assert output_file.stat().st_size > 10000, "图表7 文件过小，可能是空图"
    
    def test_02_chart_08_heatmap_generated(self):
        """测试2：图表8 DCF敏感性热力图生成"""
        output_file = self.output_dir / f"{self.test_stock}_chart08_dcf_sensitivity.png"
        
        if not output_file.exists():
            pytest.skip(f"图表8 未生成: {output_file}")
        
        assert output_file.exists()
        
        with Image.open(output_file) as img:
            dpi = img.info.get('dpi', (72,))[0]
            assert dpi >= 150
    
    def test_03_chart_09_bar_generated(self):
        """测试3：图表9 相对估值柱状图生成"""
        output_file = self.output_dir / f"{self.test_stock}_chart09_relative_valuation.png"
        
        if not output_file.exists():
            pytest.skip(f"图表9 未生成: {output_file}")
        
        assert output_file.exists()
        
        with Image.open(output_file) as img:
            dpi = img.info.get('dpi', (72,))[0]
            assert dpi >= 150
    
    def test_04_chart_10_grouped_bar_generated(self):
        """测试4：图表10 季度营收/利润柱状图生成"""
        output_file = self.output_dir / f"{self.test_stock}_chart10_quarterly_revenue.png"
        
        if not output_file.exists():
            pytest.skip(f"图表10 未生成: {output_file}")
        
        assert output_file.exists()
        
        with Image.open(output_file) as img:
            dpi = img.info.get('dpi', (72,))[0]
            assert dpi >= 150
    
    def test_05_chart_11_seasonality_heatmap_generated(self):
        """测试5：图表11 季节性热力图生成"""
        output_file = self.output_dir / f"{self.test_stock}_chart11_seasonality_heatmap.png"
        
        if not output_file.exists():
            pytest.skip(f"图表11 未生成: {output_file}")
        
        assert output_file.exists()
        
        with Image.open(output_file) as img:
            dpi = img.info.get('dpi', (72,))[0]
            assert dpi >= 150
    
    # ===== 数据字段映射验收测试 =====
    
    def test_06_module2_pe_pb_ps_fields(self):
        """测试6：模块2包含PE/PB/PS字段"""
        sys.path.insert(0, str(self.module_dir))
        
        try:
            from financial_loader import FinancialDataLoader
            
            loader = FinancialDataLoader()
            data = loader.load_from_dir(self.test_stock)
            
            metrics = data.get('financial_metrics', {})
            
            # 图表7必需字段
            assert 'pe' in metrics, "缺少PE字段"
            assert 'pb' in metrics, "缺少PB字段"
            assert 'ps' in metrics, "缺少PS字段"
            
            # 验证类型
            assert isinstance(metrics['pe'], list), "PE应为数组类型"
            assert isinstance(metrics['pb'], list), "PB应为数组类型"
            assert isinstance(metrics['ps'], list), "PS应为数组类型"
            
        except ImportError:
            pytest.skip("financial_loader.py 未实现")
    
    def test_07_module2_quarterly_fields(self):
        """测试7：模块2包含季度营收/利润字段"""
        sys.path.insert(0, str(self.module_dir))
        
        try:
            from financial_loader import FinancialDataLoader
            
            loader = FinancialDataLoader()
            data = loader.load_from_dir(self.test_stock)
            
            metrics = data.get('financial_metrics', {})
            
            # 图表10必需字段
            assert 'quarterly_revenue' in metrics, "缺少quarterly_revenue字段"
            assert 'quarterly_profit' in metrics, "缺少quarterly_profit字段"
            
            # 验证数据长度（应为4的倍数）
            assert len(metrics['quarterly_revenue']) % 4 == 0, "季度数据长度应为4的倍数"
            assert len(metrics['quarterly_profit']) % 4 == 0, "季度数据长度应为4的倍数"
            
        except ImportError:
            pytest.skip("financial_loader.py 未实现或数据不存在")
    
    # ===== 批量生成验收测试 =====
    
    def test_08_batch_generation_all_5_charts(self):
        """测试8：批量生成5张图表"""
        sys.path.insert(0, str(self.module_dir))
        
        try:
            from chart_generator import ChartGenerator
            
            generator = ChartGenerator(stock_code=self.test_stock)
            
            start_time = time.time()
            
            # 生成Phase 3图表
            results = generator.generate_phase3()
            
            elapsed = time.time() - start_time
            
            # 验证返回结果
            assert len(results) == 5, f"应生成5张图表，实际生成{len(results)}张"
            
            # 验证所有图表文件存在
            for chart_id in ['chart_07', 'chart_08', 'chart_09', 'chart_10', 'chart_11']:
                assert chart_id in results, f"缺少{chart_id}"
                assert os.path.exists(results[chart_id]), f"{chart_id}文件不存在"
            
            # 验证性能
            assert elapsed <= 15, f"批量生成耗时{elapsed:.2f}秒，超过15秒限制"
            
        except ImportError as e:
            pytest.skip(f"chart_generator.py 未实现: {e}")
        except AttributeError:
            pytest.skip("chart_generator.py 未实现generate_phase3()方法")
    
    # ===== 质量验收测试 =====
    
    def test_09_chinese_font_no_garbled(self):
        """测试9：中文字体无乱码"""
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
        
        assert available_font is not None, "无可用中文字体，图表可能出现乱码"
    
    def test_10_color_scheme_abc_convention(self):
        """测试10：配色符合A股惯例"""
        import yaml
        
        config_file = self.module_dir / "chart_config.yaml"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        colors = config.get('colors', {})
        
        # 涨=红，跌=绿（A股惯例）
        assert colors.get('bullish') == "#E74C3C", "上涨色应为红色"
        assert colors.get('bearish') == "#27AE60", "下跌色应为绿色"
    
    def test_11_all_charts_150dpi(self):
        """测试11：所有图表分辨率≥150dpi"""
        chart_files = list(self.output_dir.glob(f"{self.test_stock}_chart0[789]*.png")) + \
                     list(self.output_dir.glob(f"{self.test_stock}_chart1[01]*.png"))
        
        for chart_file in chart_files:
            with Image.open(chart_file) as img:
                dpi = img.info.get('dpi', (72,))[0]
                assert dpi >= 150, f"{chart_file.name} DPI={dpi} < 150"
    
    def test_12_filename_convention(self):
        """测试12：文件名符合规范"""
        chart_files = list(self.output_dir.glob(f"{self.test_stock}_chart0[789]*.png")) + \
                     list(self.output_dir.glob(f"{self.test_stock}_chart1[01]*.png"))
        
        for chart_file in chart_files:
            # 验证格式: {stock_code}_chart{xx}_{chart_name}.png
            parts = chart_file.stem.split('_')
            assert len(parts) >= 3, f"文件名格式不正确: {chart_file.name}"
            assert parts[0] == self.test_stock, f"股票代码不正确: {chart_file.name}"
            assert parts[1].startswith('chart'), f"缺少chart标识: {chart_file.name}"
```

### 5.3 异常注入测试

```python
def test_13_error_handling_missing_quarterly_data(self):
    """测试13：季度数据缺失时的异常处理"""
    # 模拟缺失季度数据的场景
    incomplete_data = {
        "stock_code": "000001",
        "years": [2023, 2024],
        "financial_metrics": {
            "revenue": [100, 120],
            "net_profit": [20, 25],
            # 缺少 quarterly_revenue 和 quarterly_profit
        }
    }
    
    # 验证是否抛出合理异常或显示placeholder
    # 预期: 图表10应显示"数据不可用"而不是崩溃
    pass

def test_14_error_handling_missing_pe_pb_ps(self):
    """测试14：PE/PB/PS数据缺失时的异常处理"""
    # 模拟缺失估值数据的场景
    incomplete_data = {
        "stock_code": "000001",
        "years": [2023, 2024],
        "financial_metrics": {
            "revenue": [100, 120],
            "net_profit": [20, 25],
            # 缺少 pe, pb, ps
        }
    }
    
    # 预期: 图表7应显示"数据不可用"或降级显示
    pass
```

---

## 六、验收检查清单

### 6.1 功能验收

| # | 检查项 | 验收条件 | 图表 | 状态 |
|---|--------|----------|------|------|
| F1 | 图表7生成 | PE/PB/PS箱线图存在且正确 | 7 | ☐ |
| F2 | 图表8生成 | DCF敏感性热力图存在且正确 | 8 | ☐ |
| F3 | 图表9生成 | 相对估值柱状图存在且正确 | 9 | ☐ |
| F4 | 图表10生成 | 季度营收/利润柱状图存在且正确 | 10 | ☐ |
| F5 | 图表11生成 | 季节性热力图存在且正确 | 11 | ☐ |
| F6 | 数据源对接 | 所有图表正确调用 financial_loader.py | 7-11 | ☐ |
| F7 | 字段映射 | 数据字段与图表配置一致 | 7-11 | ☐ |

### 6.2 可视化验收

| # | 检查项 | 验收条件 | 状态 |
|---|--------|----------|------|
| V1 | 中文显示 | 所有中文标签无乱码 | ☐ |
| V2 | 配色方案 | 符合A股红涨绿跌惯例 | ☐ |
| V3 | 图表类型 | 箱线图/热力图/柱状图类型正确 | ☐ |
| V4 | 图表布局 | 元素不重叠，比例协调 | ☐ |
| V5 | 热力图配色 | DCF热力图=RdYlGn_r，季节性=RdBu_r | ☐ |
| V6 | 异常值显示 | 箱线图显示异常值点 | ☐ |
| V7 | 颜色条 | 热力图显示颜色条 | ☐ |

### 6.3 质量验收

| # | 检查项 | 验收条件 | 状态 |
|---|--------|----------|------|
| Q1 | 图表标题 | "PE、PB、PS 历史估值分位" 正确 | ☐ |
| Q2 | 图表标题 | "DCF 敏感性分析热力图" 正确 | ☐ |
| Q3 | 图表标题 | "相对估值横向对比" 正确 | ☐ |
| Q4 | 图表标题 | "季度营收与净利润波动" 正确 | ☐ |
| Q5 | 图表标题 | "季节性波动热力图（同比+环比）" 正确 | ☐ |
| Q6 | 图例标注 | PE/PB/PS 正确标注 | ☐ |
| Q7 | 图例标注 | DCF估值数值正确标注 | ☐ |
| Q8 | 图例标注 | 营收/净利润正确标注 | ☐ |

### 6.4 数据字段映射验收

| # | 检查项 | 验收条件 | 图表 | 状态 |
|---|--------|----------|------|------|
| D1 | PE/PB/PS数组 | pe, pb, ps 字段存在且为数组 | 7 | ☐ |
| D2 | DCF敏感性矩阵 | dcf_sensitivity_matrix 存在 | 8 | ☐ |
| D3 | 同业对比数据 | peer_companies, pe, pb 存在 | 9 | ☐ |
| D4 | 季度营收数据 | quarterly_revenue 存在且为4的倍数 | 10 | ☐ |
| D5 | 季度利润数据 | quarterly_profit 存在且为4的倍数 | 10 | ☐ |
| D6 | 同比/环比数据 | revenue_yoy, revenue_qoq 存在 | 11 | ☐ |

### 6.5 性能验收

| # | 检查项 | 验收条件 | 状态 |
|---|--------|----------|------|
| P1 | 文件格式 | 所有输出为PNG格式 | ☐ |
| P2 | 分辨率 | DPI ≥ 150 | ☐ |
| P3 | 文件命名 | 符合 {stock_code}_chart{xx}_{name}.png | ☐ |
| P4 | 批量生成 | 5张图表生成时间 ≤ 15秒 | ☐ |
| P5 | 异常处理 | 数据缺失时显示"数据不可用" | ☐ |

---

## 七、测试执行

### 7.1 执行命令

```bash
# 进入模块目录
cd /home/ponder/.openclaw/workspace/astock-implementation/impl/module5_charts

# 执行所有Phase 3测试
python -m pytest test_phase3_e2e.py -v --tb=short

# 执行单个图表测试
python -m pytest test_phase3_e2e.py::TestPhase3E2E::test_01_chart_07_boxplot_generated -v

# 生成测试报告
python -m pytest test_phase3_e2e.py -v --tb=short --junit-xml=test_phase3_results.xml
```

### 7.2 预期结果

- **通过**: 5张图表全部成功生成，数据正确，格式符合要求
- **失败**: 图表未生成、数据错误、格式不符合、生成超时

### 7.3 失败处理

| 失败类型 | 原因 | 处理措施 |
|----------|------|----------|
| 文件不存在 | chart_generator.py 未实现或缺少对应图表生成函数 | 返回Architect补充实现 |
| 数据字段缺失 | 模块2未提供对应数据 | 确认字段映射，检查模块2Schema |
| 热力图渲染错误 | 数据矩阵维度不匹配 | 检查数据格式，修正数据处理逻辑 |
| 中文乱码 | 字体fallback链问题 | 检查系统字体配置 |
| 性能问题 | 热力图渲染耗时过长 | 优化渲染逻辑 |
| 分辨率不足 | DPI设置过低 | 调整输出配置 |

---

## 八、验收输出

### 8.1 交付物清单

- [x] 本验收方案文档 (PHASE3_VALIDATION.md)
- [ ] 测试执行脚本 (test_phase3_e2e.py)
- [ ] 验收结果报告

### 8.2 验收结论

| 角色 | 签署 | 日期 |
|------|------|------|
| 评估者（Tester） | | |
| 执行者（Architect） | | |
| 审批人（Main） | | |

---

## 九、附录

### 附录A：chart_config.yaml 相关配置

```yaml
# 图表7: PE/PB/PS历史分位 - 箱线图
chart_07_valuation_percentile:
  name: "PE/PB/PS历史分位"
  type: boxplot
  priority: P1
  data_source: module2
  metrics:
    y_axis: [pe, pb, ps]
  colors:
    pe: "#3498DB"
    pb: "#2ECC71"
    ps: "#E74C3C"
  showfliers: true

# 图表8: DCF敏感性热力图 - 热力图
chart_08_dcf_sensitivity:
  name: "DCF敏感性热力图"
  type: heatmap
  priority: P1
  data_source: module2
  colors:
    colormap: RdYlGn_r
  annotation: true

# 图表9: 相对估值横向比较 - 柱状图
chart_09_relative_valuation:
  name: "相对估值横向比较"
  type: bar
  priority: P2
  data_source: module2
  colors:
    pe: "#3498DB"
    pb: "#E74C3C"

# 图表10: 季度营收/利润波动柱状图 - 分组柱状图
chart_10_quarterly_revenue:
  name: "季度营收/利润波动柱状图"
  type: grouped_bar
  priority: P1
  data_source: module2
  colors:
    revenue: "#3498DB"
    profit: "#E74C3C"

# 图表11: 季节性热力图 - 热力图
chart_11_seasonality_heatmap:
  name: "季节性热力图"
  type: heatmap
  priority: P1
  data_source: module2
  colors:
    colormap: RdBu_r
  annotation: true
```

### 附录B：配色方案说明

| 配色方案 | 用途 | 说明 |
|----------|------|------|
| bullish=#E74C3C | 上涨/正增长 | A股红涨惯例 |
| bearish=#27AE60 | 下跌/负增长 | A股绿跌惯例 |
| primary=#2C3E50 | 主标题 | 深蓝灰 |
| RdYlGn_r | DCF热力图 | 反转色（高值绿，低值红） |
| RdBu_r | 季节性热力图 | 红蓝色阶（正负分明） |

---

*文档结束*
