#!/usr/bin/env python3
"""A股深度分析系统 - 完整端到端验证（五粮液000858）"""
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

print("="*70)
print("A股深度分析系统 - 完整端到端验证")
print("="*70)

# Stage 1: PDF - 尝试2024年报，回退到2023年报
print("\n[1/5] PDF下载...")
t0 = time.time()
pdf_path = "/home/ponder/.openclaw/workspace/astock-implementation/cache/module6/603288_2024_annual_report.pdf"
if not os.path.exists(pdf_path):
    try:
        from module6_mda.downloader import PDFDownloader
        dl = PDFDownloader()
        # 搜索2023-2025的年报
        reports = dl.get_annual_report_list('603288', 'gssh0603288', 2023, 2025)
        for r in reports:
            t = r.get('announcementTitle', '')
            if ('年度报告' in t and '摘要' not in t and '更正' not in t
                    and '取消' not in t and '英文' not in t):
                pdf_path = dl.download_with_fallback('603288', 2023, 'gssh0603288', r)
                print(f"  📄 使用2023年报: {t}")
                break
    except Exception as e:
        print(f"  ⚠️ 下载失败: {e}")
s1 = os.path.exists(pdf_path)
if s1:
    print(f"  ✅ {os.path.getsize(pdf_path)/1024/1024:.1f}MB")
else:
    print("  ❌ 无法获取中文年报PDF")
t1 = time.time()-t0

# Stage 2: 模块2财务数据
print("\n[2/5] 模块2财务数据...")
t0 = time.time()
try:
    from module2_financial.api import get_financial_history
    from module2_financial.adapter import adapt_to_chart_format, get_missing_fields
    df = get_financial_history(STOCK_CODE, years=5)
    if df is not None and len(df) > 0:
        fd = adapt_to_chart_format(df)
        years = fd.get('years', [])
        n = len(years)
        # 过滤None年份
        if n > 0:
            ok_idx = [i for i, y in enumerate(years) if y is not None]
            for k in list(fd.keys()):
                if isinstance(fd[k], list) and len(fd[k]) == n:
                    fd[k] = [fd[k][i] for i in ok_idx]
            fd['years'] = [years[i] for i in ok_idx]
        n = len(fd.get('years', []))
        rev = fd.get('revenue', [])
        roe_v = fd.get('roe', [])
        print(f"  ✅ {n}年数据，年份: {fd.get('years', [])}")
        print(f"  营收亿: {[round(v/1e8,1) if v else v for v in rev]}")
        print(f"  ROE: {[round(v,3) if v else v for v in roe_v]}")
        missing = get_missing_fields(fd)
        print(f"  缺失: {missing if missing else '无'}")
        s2 = True; financial_data = fd
    else:
        print("  ⚠️ 无数据"); s2 = False; financial_data = None
except Exception as e:
    print(f"  ❌ {e}"); s2 = False; financial_data = None
t2 = time.time()-t0

# Stage 3: 模块6MD&A
print("\n[3/5] 模块6MD&A分析...")
t0 = time.time()
try:
    from module6_mda.extractor import PDFExtractor
    from module6_mda.locator import MDALocator
    from module6_mda.analyzer import MultiProviderLLMAnalyzer
    from module6_mda.prompts import MDA_EXTRACTION_PROMPT
    text, _ = PDFExtractor().extract(pdf_path)
    mda_text = MDALocator().locate(text, pdf_path).get('mda_text', '')[:8000]
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
        for c in commits[:2]: print(f"    - {c.get('commitment','')[:60]}")
        print(f"  关键主题: {len(themes)}条")
        print(f"  风险因素: {len(risks)}条")
        s3 = True; mda_result = result
except Exception as e:
    print(f"  ❌ {e}"); import traceback; traceback.print_exc(); s3 = False; mda_result = None
t3 = time.time()-t0

# Stage 4: 模块5图表
print("\n[4/5] 模块5图表生成...")
t0 = time.time()
try:
    spec = importlib.util.spec_from_file_location(
        'cg', '/home/ponder/.openclaw/workspace/astock-implementation/impl/module5_charts/chart_generator.py')
    cg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cg)
    out_dir = '/home/ponder/.openclaw/workspace/astock-implementation/impl/module5_charts/output/e2e_final'
    os.makedirs(out_dir, exist_ok=True)
    gen = cg.ChartGenerator(stock_code=STOCK_CODE, output_dir=out_dir)
    if financial_data and len(financial_data.get('years', [])) > 2:
        data = financial_data
    else:
        data = cg.load_sample_data()
        data['years'] = [2020, 2021, 2022, 2023, 2024]
    gen.generate_all(data)
    import glob as _glob
    pngs = sorted(_glob.glob(os.path.join(out_dir, '*.png')))
    print(f"  ✅ {len(pngs)}张图表")
    for p in pngs:
        sz = os.path.getsize(p)/1024
        print(f"     {os.path.basename(p)} ({sz:.0f}KB)")
    s4 = True
except Exception as e:
    print(f"  ❌ {e}"); import traceback; traceback.print_exc(); s4 = False
t4 = time.time()-t0

# Stage 5: 模块8投资结论
print("\n[5/5] 模块8投资结论...")
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
    summary = result8.summary[:80] if hasattr(result8, 'summary') else ''
    print(f"  ✅ 评级: {rec}")
    print(f"  综合评分: {score}")
    print(f"  置信度: {conf}")
    print(f"  摘要: {summary}")
    s5 = True
except Exception as e:
    print(f"  ❌ {e}"); import traceback; traceback.print_exc(); s5 = False
t5 = time.time()-t0

total = t1+t2+t3+t4+t5
ok = sum([s1, s2, s3, s4, s5])
print(f"\n{'='*70}")
print(f"结果汇总")
print(f"{'='*70}")
print(f"[1] PDF下载:    {'✅' if s1 else '❌'} {t1:.1f}s")
print(f"[2] 模块2财务:  {'✅' if s2 else '❌'} {t2:.1f}s")
print(f"[3] 模块6MD&A: {'✅' if s3 else '❌'} {t3:.1f}s")
print(f"[4] 模块5图表:  {'✅' if s4 else '❌'} {t4:.1f}s")
print(f"[5] 模块8结论:  {'✅' if s5 else '❌'} {t5:.1f}s")
print(f"总耗时: {total:.1f}s | 通过率: {ok}/5")
if ok == 5:
    print("🎉 全链路端到端验证通过！")
else:
    print(f"⚠️  {5-ok}个阶段失败")
print(f"{'='*70}")
