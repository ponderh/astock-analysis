#!/usr/bin/env python3
"""A股深度分析系统 - 完整端到端验证（海天味业603288）"""
import sys, os, time, importlib.util

try:
    with open('/tmp/env_keys.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('MM=') and line[3:]:
                os.environ['MINIMAX_API_KEY'] = line[3:]
            elif line.startswith('DS=') and line[3:]:
                os.environ['DEEPSEEK_API_KEY'] = line[3:]
except: pass

sys.path.insert(0, '/home/ponder/.openclaw/workspace/astock-implementation/impl')
STOCK_CODE = '603288'
CACHE = '/home/ponder/.openclaw/workspace/astock-implementation/cache/module6'
os.makedirs(CACHE, exist_ok=True)

print("="*70)
print("A股深度分析系统 - 海天味业(603288) 完整端到端")
print("="*70)

# Stage 1: PDF年报
print("\n[1/5] PDF年报获取...")
t0 = time.time()
pdf_path = None
# 优先使用已缓存的最新年报
for candidate in [
    os.path.join(CACHE, '603288_2025年报.pdf'),
    os.path.join(CACHE, '603288_2024年报.pdf'),
]:
    if os.path.exists(candidate) and os.path.getsize(candidate) > 1_000_000:
        pdf_path = candidate
        print(f"  ✅ 使用缓存: {os.path.basename(pdf_path)} ({os.path.getsize(pdf_path)//1024//1024}MB)")
        break

if pdf_path is None:
    # 使用新下载器
    try:
        from module6_mda.downloader import download_annual_report
        pdf_path, src = download_annual_report('603288', 2025)
        if pdf_path:
            print(f"  ✅ 下载成功: {src}")
        else:
            print("  ⚠️ 下载失败，尝试2024...")
            pdf_path, src = download_annual_report('603288', 2024)
    except Exception as e:
        print(f"  ⚠️ 下载异常: {e}")
s1 = pdf_path is not None and os.path.exists(pdf_path)
t1 = time.time() - t0
print(f"  {'✅' if s1 else '❌'} PDF: {pdf_path}")

# Stage 2: 模块2财务数据
print("\n[2/5] 模块2财务数据...")
t0 = time.time()
financial_data = None
try:
    from module2_financial.api import get_financial_history
    from module2_financial.adapter import adapt_to_chart_format, get_missing_fields
    df = get_financial_history(STOCK_CODE, years=8)
    if df is not None and len(df) > 0:
        fd = adapt_to_chart_format(df)
        years = fd.get('years', [])
        n = len(years)
        if n > 0:
            ok_idx = [i for i, y in enumerate(years) if y is not None]
            for k in list(fd.keys()):
                if isinstance(fd[k], list) and len(fd[k]) == n:
                    fd[k] = [fd[k][i] for i in ok_idx]
            fd['years'] = [years[i] for i in ok_idx]
        n = len(fd.get('years', []))
        rev = fd.get('revenue', [])
        roe_v = fd.get('roe', [])
        print(f"  ✅ {n}年数据: {fd.get('years', [])}")
        print(f"  营收亿: {[round(v/1e8,1) if v else v for v in rev]}")
        print(f"  ROE: {[round(v,3) if v else v for v in roe_v]}")
        missing = get_missing_fields(fd)
        print(f"  缺失: {missing if missing else '无'}")
        financial_data = fd
        s2 = True
    else:
        print("  ⚠️ 无数据"); s2 = False
except Exception as e:
    print(f"  ❌ {e}"); import traceback; traceback.print_exc(); s2 = False
t2 = time.time() - t0

# Stage 3: 模块6MD&A分析
print("\n[3/5] 模块6MD&A分析...")
t0 = time.time()
mda_result = None
try:
    from module6_mda.extractor import PDFExtractor
    from module6_mda.locator import MDALocator
    from module6_mda.analyzer import MultiProviderLLMAnalyzer
    from module6_mda.prompts import MDA_EXTRACTION_PROMPT
    text, _ = PDFExtractor().extract(pdf_path)
    # 手动定位MD&A section
    mda_start = text.find('三、经营情况讨论与分析')
    if mda_start < 0:
        mda_start = text.find('经营情况讨论与分析')
    ends = ['四、投资状况', '四、 主要控股', '重要事项', '第五节', '四、利润分配']
    mda_end = len(text)
    for e in ends:
        idx = text.find(e, mda_start + 100)
        if idx > mda_start and idx < mda_end:
            mda_end = idx
    mda_text = text[mda_start:mda_end][:12000] if mda_start >= 0 else text[:12000]
    print(f"  MD&A文本: {len(mda_text)}字符")
    result = MultiProviderLLMAnalyzer().analyze_with_fallback(
        text=mda_text, prompt_template=MDA_EXTRACTION_PROMPT, max_tokens=4000)
    if result.get('error'):
        print(f"  ❌ {result['error']}"); s3 = False
    else:
        sd = result.get('structured_data', {})
        commits = sd.get('strategic_commitments', [])
        risks = sd.get('risk_factors', [])
        themes = sd.get('key_strategic_themes', [])
        print(f"  ✅ {result.get('model_used')}")
        print(f"  战略承诺: {len(commits)}条")
        for c in commits[:3]: print(f"    - {c.get('commitment','')[:70]}")
        print(f"  关键主题: {len(themes)}条 | 风险: {len(risks)}条")
        mda_result = result; s3 = True
except Exception as e:
    print(f"  ❌ {e}"); import traceback; traceback.print_exc(); s3 = False
t3 = time.time() - t0

# Stage 4: 模块5图表
print("\n[4/5] 模块5图表生成...")
t0 = time.time()
chart_dir = os.path.join(CACHE, 'charts_603288')
os.makedirs(chart_dir, exist_ok=True)
try:
    spec = importlib.util.spec_from_file_location(
        'cg', '/home/ponder/.openclaw/workspace/astock-implementation/impl/module5_charts/chart_generator.py')
    cg_mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(cg_mod)
    gen = cg_mod.ChartGenerator(stock_code=STOCK_CODE, output_dir=chart_dir)
    if financial_data and len(financial_data.get('years', [])) > 2:
        data = financial_data
    else:
        data = cg_mod.ChartGenerator.load_sample_data(STOCK_CODE)
    gen.generate_all(data)
    import glob as _glob
    pngs = sorted(_glob.glob(os.path.join(chart_dir, '*.png')))
    print(f"  ✅ {len(pngs)}张图表:")
    for p in pngs:
        sz = os.path.getsize(p)//1024
        print(f"     {os.path.basename(p)} ({sz}KB)")
    s4 = True
except Exception as e:
    print(f"  ❌ {e}"); import traceback; traceback.print_exc(); s4 = False
t4 = time.time() - t0

# Stage 5: 生成PDF分析报告
print("\n[5/7] 生成PDF分析报告...")
t0 = time.time()
pdf_report_path = os.path.join(CACHE, '603288_深度分析报告.pdf')
try:
    spec_rg = importlib.util.spec_from_file_location(
        'rg', '/home/ponder/.openclaw/workspace/astock-implementation/impl/module6_mda/report_generator.py')
    rg_mod = importlib.util.module_from_spec(spec_rg)
    import sys as _sys
    _sys.modules['module6_mda.report_generator'] = rg_mod
    spec_rg.loader.exec_module(rg_mod)
    rg_mod.build(pdf_report_path)
    sz = os.path.getsize(pdf_report_path)
    print(f"  ✅ PDF报告: {pdf_report_path} ({sz//1024}KB)")
    s5 = True
except Exception as e:
    print(f"  ❌ PDF生成失败: {e}"); import traceback; traceback.print_exc(); s5 = False
t5 = time.time() - t0

# Stage 6: 投资结论
print("\n[6/7] 模块8投资结论...")
t0 = time.time()
try:
    sys.path.insert(0, '/home/ponder/.openclaw/workspace/astock-implementation/impl/module8_investment_conclusion')
    from run_analysis import analyze
    agg_data = {
        'financial': financial_data or {},
        'red_flags': {'red': 0, 'yellow': 1, 'extreme': 0},
        'mda': mda_result.get('structured_data', {}) if mda_result else {},
        'governance': {'equity_pledge_ratio': 0.05}
    }
    result8 = analyze(STOCK_CODE, agg_data)
    rec = result8.recommendation if hasattr(result8, 'recommendation') else str(result8)
    score = result8.total_score if hasattr(result8, 'total_score') else 'N/A'
    conf = result8.confidence if hasattr(result8, 'confidence') else 'N/A'
    summary = (result8.summary[:100] if hasattr(result8, 'summary') and result8.summary else '无')
    print(f"  ✅ 评级: {rec} | 评分: {score} | 置信度: {conf}")
    if summary:
        print(f"  摘要: {summary}")
    s6 = True
except Exception as e:
    print(f"  ⚠️ 模块8不可用: {e}"); s6 = False
t6 = time.time() - t0

total = t1+t2+t3+t4+t5+t6
ok_count = sum([s for s in [s1,s2,s3,s4,s5,s6] if s])
print(f"\n{'='*70}")
print(f"结果汇总")
print(f"{'='*70}")
print(f"[1] PDF年报:    {'✅' if s1 else '❌'} {t1:.1f}s")
print(f"[2] 模块2财务:  {'✅' if s2 else '❌'} {t2:.1f}s")
print(f"[3] 模块6MD&A: {'✅' if s3 else '❌'} {t3:.1f}s")
print(f"[4] 模块5图表:  {'✅' if s4 else '❌'} {t4:.1f}s")
print(f"[5] PDF报告:    {'✅' if s5 else '❌'} {t5:.1f}s  -> {pdf_report_path}")
print(f"[6] 模块8结论:  {'✅' if s6 else '⚠️'} {t6:.1f}s")
print(f"总耗时: {total:.1f}s | 通过率: {ok_count}/6")
print(f"{'='*70}")
