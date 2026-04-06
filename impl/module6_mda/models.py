"""
module6_mda 数据模型
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from enum import Enum


class PipelineStage(Enum):
    DOWNLOAD = "download"
    EXTRACT = "extract"
    LOCATE = "locate"
    ANALYZE = "analyze"
    SCORE = "score"


class ExtractionMethod(Enum):
    """文字提取方法"""
    PYMUPDF = "pymupdf"
    PDFPLUMBER = "pdfplumber"
    PADDLEOCR = "paddleocr"
    TESSERACT = "tesseract"
    MANUAL = "manual"


class LocationMethod(Enum):
    """章节定位方法"""
    TOC = "toc"
    HIERARCHY = "hierarchy"
    KEYWORD = "keyword"
    FONT = "font"
    FALLBACK = "fallback"
    FALLBACK_FULL = "fallback_full"
    NONE = "none"


@dataclass
class StageResult:
    """单个阶段结果"""
    stage: PipelineStage
    success: bool
    method: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PDFInfo:
    """PDF文件信息"""
    stock_code: str
    year: int
    announcement_id: str
    title: str
    announcement_time: int  # milliseconds
    pdf_url: str
    local_path: Optional[str] = None
    file_size: Optional[int] = None


@dataclass
class MDASection:
    """MD&A章节"""
    full_text: str
    char_count: int
    location_method: LocationMethod
    subsections: Dict[str, str] = field(default_factory=dict)
    # 关键子节
    strategy_text: str = ""
    risk_text: str = ""
    operation_text: str = ""


@dataclass
class StrategicAnalysis:
    """战略分析结果"""
    raw_llm_response: str
    structured_data: Dict[str, Any]
    model_used: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    hallucination_flags: List[str] = field(default_factory=list)


@dataclass
class QualityScore:
    """质量评分"""
    overall_score: float  # 0-1
    grade: str  # A/B/C/D
    char_count_score: float
    structure_score: float
    key_paragraph_score: float
    semantic_score: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MDAResult:
    """完整MD&A处理结果"""
    stock_code: str
    year: int
    pdf_info: Optional[PDFInfo] = None

    # 管道各阶段
    download_result: Optional[StageResult] = None
    extract_result: Optional[StageResult] = None
    locate_result: Optional[StageResult] = None
    analyze_result: Optional[StageResult] = None
    score_result: Optional[StageResult] = None

    # 内容
    mda_section: Optional[MDASection] = None
    strategic_analysis: Optional[StrategicAnalysis] = None
    quality_score: Optional[QualityScore] = None

    @property
    def success(self) -> bool:
        return (
            self.download_result is not None and self.download_result.success and
            self.extract_result is not None and self.extract_result.success and
            self.locate_result is not None and self.locate_result.success
        )

    @property
    def end_to_end_success(self) -> bool:
        return (
            self.success and
            self.analyze_result is not None and self.analyze_result.success and
            self.quality_score is not None and self.quality_score.overall_score >= 0.5
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stock_code': self.stock_code,
            'year': self.year,
            'success': self.success,
            'end_to_end_success': self.end_to_end_success,
            'stages': {
                'download': self.download_result.success if self.download_result else False,
                'extract': self.extract_result.success if self.extract_result else False,
                'locate': self.locate_result.success if self.locate_result else False,
                'analyze': self.analyze_result.success if self.analyze_result else False,
                'score': self.score_result.success if self.score_result else False,
            },
            'quality_score': self.quality_score.overall_score if self.quality_score else None,
            'quality_grade': self.quality_score.grade if self.quality_score else None,
        }
