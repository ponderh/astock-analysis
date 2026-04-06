#!/usr/bin/env python3
"""
P0.5 端到端集成验证 v2
数据流：PDF下载 → 模块2财务数据 → 模块6MD&A分析 → 模块5图表生成
"""
import sys, os, time, importlib.util

# 读取环境变量
try:
    with open('/tmp/env_keys.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('MM=') and line[3:]:
                os.environ['MINIMAX_API_KEY'] = line[3:]
            elif line.startswith('DS=') and line[3:]:
                os.environ['DEEPSEEK_API_KEY'] = line[3:]
except:
    pass

sys.path.insert(0, '/home/ponder/.openclaw/workspace/astock-implementation/impl')

STOCK_CODE = '000858'
YEAR = 2024

print("="*70)
print("P0.5 端到端集成验证 v2 - 五粮液(000858) 2024年报")
print("="*70)

# ========== Stage 1: PDF下载 ==========
print("\n[Stage 1] PDF下载...")
t0 = time.time()
pdf_path = f"/home/ponder/.openclaw/workspace/astock-implementation/cache/module6/{STOCK_CODE}_{YEAR}_annual_report.pdf"
if os.path.exists(pdf_path):
    print(f"  ✅ 使用缓存: {os.path.getsize(pdf_path)/1024/1024:.1f}MB")
    stage1_ok = True
else:
    print("  ❌ PDF不存在"); stage1_ok = False
stage1_time = time.time() - t0

# ========== Stage 2: 模块2财务数据 ==========
print("\n[Stage 2] 模块2财务数据...")
t1 = time.time()
try:
    from module2_financial.api import get_financial_history
    df = get_financial_history(STOCK_CODE, years=5)
    if df is not None and len(df) > 0:
        print(f"  ✅ 获取到 {len(df)} 行财务数据")
        cols = list(df.columns)
        print(f"  列名: {cols[:8]}...")
        if 'statDate' in cols:
            print(f"  年份: {df['statDate'].tolist()[:5]}")
        stage2_ok = True
    else:
        print("  ⚠️ 模块2返回空DataFrame")
        stage2_ok = False
        df = None
except Exception as e:
    print(f"  ⚠️ 模块2失败: {e}")
    stage2_ok = False
    df = None
stage2_time = time.time() - t1

# ========== Stage 3: 模块6MD&A分析 ==========
print("\n[Stage 3] 模块6MD&A分析...")
t2 = time.time()
try:
    from module6_mda.extractor import PDFExtractor
    from module6_mda.locator import MDALocator
    from module6_mda.analyzer import MultiProviderLLMAnalyzer
    from module6_mda.prompts import MDA_EXTRACTION_PROMPT

    extractor = PDFExtractor()
    text, _ = extractor.extract(pdf_path)

    locator = MDALocator()
    locate_result = locator.locate(text, pdf_path)
    mda_text = locate_result.get('mda_text', '')[:8000]
    print(f"  定位: {len(mda_text)}字符 (置信度:{locate_result.get('confidence',0):.2f})")

    analyzer = MultiProviderLLMAnalyzer()
    result = analyzer.analyze_with_fallback(
        text=mda_text,
        prompt_template=MDA_EXTRACTION_PROMPT,
        max_tokens=4000
    )

    if result.get('error'):
        print(f"  ❌ LLM失败: {result['error']}")
        stage3_ok = False
    else:
        sd = result.get('structured_data', {})
        commits = sd.get('strategic_commitments', [])
        themes = sd.get('key_strategic_themes', [])
        risks = sd.get('risk_factors', [])
        print(f"  ✅ LLM成功 | 模型: {result.get('model_used')}")
        print(f"     战略承诺: {len(commits)}条")
        print(f"     关键主题: {len(themes)}条")
        print(f"     风险因素: {len(risks)}条")
        if commits:
            print(f"     示例承诺: {commits[0].get('commitment','')[:60]}")
        stage3_ok = True
        mda_result = result
except Exception as e:
    print(f"  ❌ 模块6失败: {e}")
    import traceback; traceback.print_exc()
    stage3_ok = False
    mda_result = None
stage3_time = time.time() - t2

# ========== Stage 4: 模块5图表 ==========
print("\n[Stage 4] 模块5图表生成...")
t3 = time.time()
try:
    spec = importlib.util.spec_from_file_location(
        'chart_generator',
        '/home/ponder/.openclaw/workspace/astock-implementation/impl/module5_charts/chart_generator.py'
    )
    cg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cg)

    output_dir = '/home/ponder/.openclaw/workspace/astock-implementation/impl/module5_charts/output/e2e_v2'
    os.makedirs(output_dir, exist_ok=True)

    generator = cg.ChartGenerator(stock_code=STOCK_CODE, output_dir=output_dir)

    # 使用示例数据（模块2真实数据格式待适配）
    data = cg.load_sample_data()
    data['years'] = [2020, 2021, 2022, 2023, 2024]

    results = generator.generate_all(data)

    import glob
    pngs = sorted(glob.glob(os.path.join(output_dir, '*.png')))
    print(f"  ✅ 生成 {len(pngs)} 张图表")
    for p in pngs:
        print(f"     {os.path.basename(p)} ({os.path.getsize(p)/1024:.0f}KB)")
    stage4_ok = True
except Exception as e:
    print(f"  ❌ 模块5失败: {e}")
    import traceback; traceback.print_exc()
    stage4_ok = False
stage4_time = time.time() - t3

# ========== 汇总 ==========
total = stage1_time + stage2_time + stage3_time + stage4_time
print("\n" + "="*70)
print("P0.5 端到端集成验证结果")
print("="*70)
print(f"Stage 1 PDF下载:    {'✅' if stage1_ok else '❌'} {stage1_time:.1f}s")
print(f"Stage 2 模块2财务:  {'✅' if stage2_ok else '⚠️'} {stage2_time:.1f}s")
print(f"Stage 3 模块6MD&A: {'✅' if stage3_ok else '❌'} {stage3_time:.1f}s")
print(f"Stage 4 模块5图表:  {'✅' if stage4_ok else '❌'} {stage4_time:.1f}s")
print(f"\n总耗时: {total:.1f}s")
print("\n待解决问题:")
if not stage2_ok:
    print("  [P0] 模块2 get_financial_history返回空 - HDF5数据可用性待确认")
if stage3_ok and mda_result:
    sd = mda_result.get('structured_data', {})
    if len(sd.get('strategic_commitments', [])) == 0:
        print("  [P1] MD&A战略承诺0条 - 可能是Prompt格式或文本切分问题")
print("="*70)
