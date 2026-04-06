#!/usr/bin/env python3
"""
P0.5 端到端验证脚本
验证 MiniMax M2.7 + DeepSeek 双验证模式是否正常工作
"""
import os, sys, subprocess, logging

# 从 bashrc 加载环境变量
r1 = subprocess.run(['bash', '-i', '-c', 'echo MINIMAX_API_KEY=$MINIMAX_API_KEY'],
                    capture_output=True, text=True, timeout=5)
for l in r1.stdout.strip().split('\n'):
    if l.startswith('MINIMAX_API_KEY=') and '(not set)' not in l:
        os.environ['MINIMAX_API_KEY'] = l.split('=', 1)[1]

r2 = subprocess.run(['bash', '-i', '-c', 'echo DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY'],
                    capture_output=True, text=True, timeout=5)
for l in r2.stdout.strip().split('\n'):
    if l.startswith('DEEPSEEK_API_KEY=') and '(not set)' not in l:
        os.environ['DEEPSEEK_API_KEY'] = l.split('=', 1)[1]

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
sys.path.insert(0, '/home/ponder/.openclaw/workspace/astock-implementation/impl/module6_mda')

from pipeline import MDAPipeline

# 用永新股份(002014) 深市股票
pipeline = MDAPipeline(
    stock_code='002014',
    org_id='gssz002014'
)

print("\n" + "="*70)
print("P0.5 端到端验证 - 永新股份(002014) 2024年报")
print("="*70)
print(f"MINIMAX_API_KEY: {'✓' if os.environ.get('MINIMAX_API_KEY') else '✗'}")
print(f"DEEPSEEK_API_KEY: {'✓' if os.environ.get('DEEPSEEK_API_KEY') else '✗'}")

print("\n开始处理...")
result = pipeline.process_one_year(2024)

print("\n" + "="*70)
print("结果汇总")
print("="*70)
print(f"端到端成功: {result.end_to_end_success}")
print(f"PDF下载: {'✅' if result.download_result and result.download_result.success else '❌'} {result.download_result.method if result.download_result else 'N/A'}")
print(f"文字提取: {'✅' if result.extract_result and result.extract_result.success else '❌'} {result.extract_result.method if result.extract_result else 'N/A'}")
print(f"章节定位: {'✅' if result.locate_result and result.locate_result.success else '❌'} {result.locate_result.method if result.locate_result else 'N/A'} (置信度: {result.locate_result.metadata.get('confidence', 0) if result.locate_result else 0:.2f})")
print(f"LLM分析: {'✅' if result.analyze_result and result.analyze_result.success else '❌'} {result.analyze_result.method if result.analyze_result else 'N/A'}")
if result.analyze_result:
    print(f"  模型: {result.analyze_result.metadata.get('model', 'N/A')}")
    flags = result.analyze_result.metadata.get('hallucination_flags', [])
    print(f"  幻觉标记: {flags if flags else '无'}")
print(f"质量评分: {result.quality_score.grade if result.quality_score else 'N/A'} ({result.quality_score.overall_score if result.quality_score else 0:.3f})")
print(f"MD&A字符数: {result.mda_section.char_count if result.mda_section else 0}")

print("\n--- Strategic Analysis ---")
if result.strategic_analysis and result.strategic_analysis.structured_data:
    sd = result.strategic_analysis.structured_data
    commits = sd.get('strategic_commitments', [])
    themes = sd.get('key_strategic_themes', [])
    risks = sd.get('risk_factors', [])
    print(f"战略承诺: {len(commits)}条")
    print(f"关键主题: {len(themes)}条")
    print(f"风险因素: {len(risks)}条")
    if commits:
        print(f"  第一条: {commits[0].get('commitment', '')[:80]}")
    print(f"原始模型: {result.strategic_analysis.model_used}")
else:
    print("无结构化数据")

print("\n--- analyze_with_validation (MiniMax vs DeepSeek) ---")
if result.strategic_analysis and result.mda_section:
    text = result.mda_section.strategy_text or result.mda_section.full_text[:3000]
    try:
        from analyzer import MultiProviderLLMAnalyzer
        validator = MultiProviderLLMAnalyzer()
        validation = validator.analyze_with_validation(
            text=text,
            prompt_template="请用JSON格式提取：战略承诺、关键主题、风险因素。{text}",
            max_tokens=2000
        )
        print(f"验证状态: {validation['validation_status']}")
        print(f"一致性: {validation['consistency']}")
        for k, v in validation['results'].items():
            print(f"  {k}: {v['model']} | {v['raw'][:150]}...")
    except Exception as e:
        print(f"验证失败: {e}")
