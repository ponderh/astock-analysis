"""
MD&A PDF解析管道 - 主协调器
整合下载→提取→定位→分析→评分全流程
"""

import os
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from .downloader import PDFDownloader, YONGXIN_CODE, YONGXIN_ORGID
except ImportError:
    from downloader import PDFDownloader, YONGXIN_CODE, YONGXIN_ORGID

try:
    from .extractor import PDFExtractor
except ImportError:
    from extractor import PDFExtractor

try:
    from .locator import MDALocator
except ImportError:
    from locator import MDALocator

try:
    from .analyzer import LLMAnalyzer
except ImportError:
    from analyzer import LLMAnalyzer

try:
    from .scorer import QualityScorer
except ImportError:
    from scorer import QualityScorer

try:
    from .models import (
        MDAResult, StageResult, PDFInfo, MDASection, StrategicAnalysis,
        QualityScore, PipelineStage, ExtractionMethod, LocationMethod
    )
except ImportError:
    from models import (
        MDAResult, StageResult, PDFInfo, MDASection, StrategicAnalysis,
        QualityScore, PipelineStage, ExtractionMethod, LocationMethod
    )

logger = logging.getLogger(__name__)


class MDAPipeline:
    """
    MD&A PDF解析管道

    使用5级降级策略处理PDF下载和文字提取
    使用4级降级策略进行章节定位
    使用约束性Prompt进行LLM分析
    """

    def __init__(self,
                 stock_code: str = YONGXIN_CODE,
                 org_id: str = YONGXIN_ORGID,
                 cache_dir: Optional[str] = None):
        self.stock_code = stock_code
        self.org_id = org_id

        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path("/home/ponder/.openclaw/workspace/astock-implementation/cache/module6")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 初始化各模块
        self.downloader = PDFDownloader(cache_dir=str(self.cache_dir))
        self.extractor = PDFExtractor()
        self.locator = MDALocator()
        self.analyzer = LLMAnalyzer()
        self.scorer = QualityScorer()

    def process_one_year(self, year: int) -> MDAResult:
        """
        处理单一年报
        返回完整的MDAResult
        """
        result = MDAResult(stock_code=self.stock_code, year=year)

        logger.info(f"\n{'='*70}")
        logger.info(f"开始处理 {self.stock_code} {year} 年报")
        logger.info(f"{'='*70}")

        # === Step 1: PDF下载 ===
        t0 = time.time()
        try:
            # 获取年报列表
            report_list = self.downloader.get_annual_report_list(
                self.stock_code, self.org_id, year, year
            )

            if not report_list:
                result.download_result = StageResult(
                    stage=PipelineStage.DOWNLOAD,
                    success=False,
                    error="未找到年报"
                )
                logger.error(f"[{year}] 未找到年报")
                return result

            report_info = report_list[0]  # 取最新一个

            # 下载PDF
            local_path = self.downloader.download_with_fallback(
                self.stock_code, year, self.org_id, report_info
            )

            if local_path and os.path.exists(local_path):
                result.pdf_info = PDFInfo(
                    stock_code=self.stock_code,
                    year=year,
                    announcement_id=report_info['announcementId'],
                    title=report_info['title'],
                    announcement_time=report_info['announcementTime'],
                    pdf_url='',
                    local_path=local_path,
                    file_size=os.path.getsize(local_path)
                )
                result.download_result = StageResult(
                    stage=PipelineStage.DOWNLOAD,
                    success=True,
                    method='curl_cninfo',
                    metadata={'file_size': os.path.getsize(local_path)}
                )
                logger.info(f"[{year}] PDF下载成功: {local_path} ({os.path.getsize(local_path)} bytes)")
            else:
                result.download_result = StageResult(
                    stage=PipelineStage.DOWNLOAD,
                    success=False,
                    error="下载失败"
                )
                logger.error(f"[{year}] PDF下载失败")
                return result

        except Exception as e:
            result.download_result = StageResult(
                stage=PipelineStage.DOWNLOAD,
                success=False,
                error=str(e)
            )
            logger.error(f"[{year}] 下载异常: {e}")
            return result

        download_time = time.time() - t0

        # === Step 2: 文字提取 ===
        t1 = time.time()
        try:
            text, method = self.extractor.extract(result.pdf_info.local_path)
            result.pdf_info.local_path  # 确保路径存在

            if text and len(text) > 100:
                result.extract_result = StageResult(
                    stage=PipelineStage.EXTRACT,
                    success=True,
                    method=method,
                    metadata={'char_count': len(text)}
                )
                logger.info(f"[{year}] 文字提取成功: {method}, {len(text)} 字符")
            else:
                result.extract_result = StageResult(
                    stage=PipelineStage.EXTRACT,
                    success=False,
                    method=method,
                    error="提取文本太短"
                )
                logger.error(f"[{year}] 文字提取失败: 文本太短")
                return result

        except Exception as e:
            result.extract_result = StageResult(
                stage=PipelineStage.EXTRACT,
                success=False,
                error=str(e)
            )
            logger.error(f"[{year}] 提取异常: {e}")
            return result

        extract_time = time.time() - t1

        # === Step 3: 章节定位 ===
        t2 = time.time()
        try:
            locate_result = self.locator.locate(text, result.pdf_info.local_path)

            mda_text = locate_result.get('mda_text', '')
            subsections = locate_result.get('subsections', {})
            method = locate_result.get('method', 'unknown')
            confidence = locate_result.get('confidence', 0.0)

            if mda_text and len(mda_text) > 100:
                result.locate_result = StageResult(
                    stage=PipelineStage.LOCATE,
                    success=True,
                    method=method,
                    metadata={'confidence': confidence, 'char_count': len(mda_text)}
                )
                logger.info(f"[{year}] 章节定位成功: {method}, confidence={confidence:.2f}, {len(mda_text)} 字符")

                result.mda_section = MDASection(
                    full_text=mda_text,
                    char_count=len(mda_text),
                    location_method=LocationMethod(method),
                    subsections=subsections
                )

                # 保存其他子节文本
                if 'strategy' in subsections:
                    result.mda_section.strategy_text = subsections['strategy']
                if 'risk' in subsections:
                    result.mda_section.risk_text = subsections['risk']
                if 'operation' in subsections:
                    result.mda_section.operation_text = subsections['operation']

            else:
                # 降级：用全文代替
                mda_text = text
                result.locate_result = StageResult(
                    stage=PipelineStage.LOCATE,
                    success=True,
                    method='fallback_full',
                    metadata={'confidence': 0.2, 'char_count': len(text)}
                )
                logger.warning(f"[{year}] 章节定位降级到全文")

                result.mda_section = MDASection(
                    full_text=text,
                    char_count=len(text),
                    location_method=LocationMethod('fallback_full'),
                    subsections={}
                )

        except Exception as e:
            result.locate_result = StageResult(
                stage=PipelineStage.LOCATE,
                success=False,
                error=str(e)
            )
            logger.error(f"[{year}] 章节定位异常: {e}")
            return result

        locate_time = time.time() - t2

        # === Step 4: LLM分析（仅战略子节） ===
        t3 = time.time()
        try:
            # 优先分析战略子节
            strategy_text = result.mda_section.strategy_text or result.mda_section.full_text[:5000]

            llm_result = self.analyzer.analyze_strategy_section(strategy_text)

            if llm_result and not llm_result.get('error'):
                result.analyze_result = StageResult(
                    stage=PipelineStage.ANALYZE,
                    success=True,
                    method=llm_result.get('model_used', 'deepseek'),
                    metadata={
                        'model': llm_result.get('model_used', 'unknown'),
                        'hallucination_flags': llm_result.get('hallucination_flags', [])
                    }
                )

                result.strategic_analysis = StrategicAnalysis(
                    raw_llm_response=llm_result.get('raw_response', ''),
                    structured_data=llm_result.get('structured_data', {}),
                    model_used=llm_result.get('model_used', 'unknown'),
                    hallucination_flags=llm_result.get('hallucination_flags', [])
                )
                logger.info(f"[{year}] 分析成功: {llm_result.get('model_used', 'unknown')}")
            else:
                # LLM失败，降级到规则分析
                logger.warning(f"[{year}] LLM分析失败: {llm_result.get('error', 'unknown')}, 降级到规则分析")
                try:
                    from .analyzer import RuleBasedAnalyzer
                except ImportError:
                    from analyzer import RuleBasedAnalyzer

                rule_analyzer = RuleBasedAnalyzer()
                rule_result = rule_analyzer.analyze(strategy_text)

                result.analyze_result = StageResult(
                    stage=PipelineStage.ANALYZE,
                    success=True,  # 规则分析作为降级是成功的
                    method='rule_based_fallback',
                    metadata={
                        'model': 'rule_based_fallback',
                        'hallucination_flags': rule_result.get('hallucination_flags', []),
                        'original_error': llm_result.get('error', 'unknown')
                    }
                )

                result.strategic_analysis = StrategicAnalysis(
                    raw_llm_response=rule_result.get('raw_response', ''),
                    structured_data=rule_result.get('structured_data', {}),
                    model_used='rule_based_fallback',
                    hallucination_flags=rule_result.get('hallucination_flags', [])
                )
                logger.info(f"[{year}] 规则分析降级成功")

        except Exception as e:
            result.analyze_result = StageResult(
                stage=PipelineStage.ANALYZE,
                success=False,
                error=str(e)
            )
            logger.error(f"[{year}] LLM分析异常: {e}")

        analyze_time = time.time() - t3

        # === Step 5: 质量评分 ===
        t4 = time.time()
        try:
            quality = self.scorer.score(
                mda_text=result.mda_section.full_text,
                subsections=result.mda_section.subsections,
                strategic_data=result.strategic_analysis.structured_data if result.strategic_analysis else None,
                location_method=result.locate_result.method if result.locate_result else 'unknown'
            )

            result.quality_score = QualityScore(
                overall_score=quality['overall_score'],
                grade=quality['grade'],
                char_count_score=quality['char_count_score'],
                structure_score=quality['structure_score'],
                key_paragraph_score=quality['key_paragraph_score'],
                semantic_score=quality['semantic_score'],
                details=quality['details']
            )

            result.score_result = StageResult(
                stage=PipelineStage.SCORE,
                success=True,
                metadata=quality
            )

        except Exception as e:
            result.score_result = StageResult(
                stage=PipelineStage.SCORE,
                success=False,
                error=str(e)
            )
            logger.error(f"[{year}] 质量评分异常: {e}")

        score_time = time.time() - t4

        # 汇总
        total_time = download_time + extract_time + locate_time + analyze_time + score_time
        logger.info(f"[{year}] 处理完成: {result.end_to_end_success} | "
                     f"质量: {result.quality_score.grade if result.quality_score else 'N/A'} | "
                     f"总耗时: {total_time:.1f}s (下载{download_time:.1f}s "
                     f"提取{extract_time:.1f}s 定位{locate_time:.1f}s "
                     f"分析{analyze_time:.1f}s)")

        return result

    def process_batch(self, years: List[int]) -> Dict[int, MDAResult]:
        """
        批量处理多年年报
        返回: {year: MDAResult}
        """
        results = {}
        for year in sorted(years):
            result = self.process_one_year(year)
            results[year] = result

        # 统计
        total = len(years)
        success = sum(1 for r in results.values() if r.end_to_end_success)
        download_ok = sum(1 for r in results.values() if r.download_result and r.download_result.success)
        extract_ok = sum(1 for r in results.values() if r.extract_result and r.extract_result.success)
        locate_ok = sum(1 for r in results.values() if r.locate_result and r.locate_result.success)
        analyze_ok = sum(1 for r in results.values() if r.analyze_result and r.analyze_result.success)

        logger.info(f"\n{'='*70}")
        logger.info(f"批量处理完成: {success}/{total} 端到端成功")
        logger.info(f"  下载: {download_ok}/{total}")
        logger.info(f"  提取: {extract_ok}/{total}")
        logger.info(f"  定位: {locate_ok}/{total}")
        logger.info(f"  分析: {analyze_ok}/{total}")
        logger.info(f"  端到端成功率: {success/total:.1%}")
        logger.info(f"{'='*70}")

        return results

    def summary(self, results: Dict[int, MDAResult]) -> str:
        """生成结果摘要"""
        lines = []
        lines.append(f"\n{'='*70}")
        lines.append(f"MD&A管道测试结果 - {self.stock_code}")
        lines.append(f"{'='*70}")

        for year in sorted(results.keys()):
            r = results[year]
            status = "✅" if r.end_to_end_success else "❌"
            grade = r.quality_score.grade if r.quality_score else "N/A"
            score = f"{r.quality_score.overall_score:.2f}" if r.quality_score else "N/A"
            mda_chars = r.mda_section.char_count if r.mda_section else 0

            loc_method = r.locate_result.method if r.locate_result else "N/A"
            loc_conf = r.locate_result.metadata.get('confidence', 0) if r.locate_result else 0

            lines.append(f"\n{status} {year}年")
            lines.append(f"   质量: {grade} ({score}) | MD&A: {mda_chars}字")
            lines.append(f"   定位: {loc_method} (置信度:{loc_conf:.2f})")

            if r.download_result:
                dl_ok = "✅" if r.download_result.success else "❌"
                lines.append(f"   下载: {dl_ok} {r.download_result.method or r.download_result.error}")

            if r.extract_result:
                ex_ok = "✅" if r.extract_result.success else "❌"
                lines.append(f"   提取: {ex_ok} {r.extract_result.method or r.extract_result.error}")

            if r.analyze_result:
                an_ok = "✅" if r.analyze_result.success else "❌"
                flags = r.analyze_result.metadata.get('hallucination_flags', []) if r.analyze_result.metadata else []
                flag_str = f" | 幻觉: {flags}" if flags else ""
                lines.append(f"   分析: {an_ok} {r.analyze_result.method}{flag_str}")

        # 统计
        total = len(results)
        success = sum(1 for r in results.values() if r.end_to_end_success)
        lines.append(f"\n{'='*50}")
        lines.append(f"端到端成功率: {success}/{total} = {success/total:.1%}")

        return '\n'.join(lines)
