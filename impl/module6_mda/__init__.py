"""
MD&A PDF解析管道 - module6
永新股份(002014)原型验证

5级降级: PyMuPDF → pdfplumber → PaddleOCR → Tesseract → 人工
4级章节定位: TOC书签 → 层级推断 → 关键词 → 字体特征
"""

from .pipeline import MDAPipeline

__all__ = ['MDAPipeline']
