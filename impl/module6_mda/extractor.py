"""
文字提取器 - 3级降级策略
Level 1: PyMuPDF (fitz)
Level 2: pdfplumber
Level 3: PaddleOCR
Fallback: Tesseract / 人工
"""

import os
import logging
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class PDFExtractor:
    """
    PDF文字提取器，支持多级降级
    """

    def __init__(self):
        self._pymupdf_available = None
        self._pdfplumber_available = None
        self._paddleocr_available = None
        self._tesseract_available = None

        self._check_dependencies()

    def _check_dependencies(self):
        """检查各依赖是否可用"""
        try:
            import fitz
            self._pymupdf_available = True
            logger.info("PyMuPDF: 可用")
        except ImportError:
            self._pymupdf_available = False
            logger.warning("PyMuPDF: 不可用")

        try:
            import pdfplumber
            self._pdfplumber_available = True
            logger.info("pdfplumber: 可用")
        except ImportError:
            self._pdfplumber_available = False
            logger.warning("pdfplumber: 不可用")

        try:
            import paddleocr
            self._paddleocr_available = True
            logger.info("PaddleOCR: 可用")
        except ImportError:
            self._paddleocr_available = False
            logger.warning("PaddleOCR: 不可用")

        try:
            import pytesseract
            self._tesseract_available = True
            logger.info("Tesseract: 可用")
        except ImportError:
            self._tesseract_available = False
            logger.warning("Tesseract: 不可用")

    def extract(self, pdf_path: str) -> Tuple[Optional[str], str]:
        """
        提取PDF全文文字
        返回: (text, method)
        """
        if not os.path.exists(pdf_path):
            logger.error(f"PDF文件不存在: {pdf_path}")
            return None, "file_not_found"

        # === Level 1: PyMuPDF ===
        if self._pymupdf_available:
            text = self._extract_pymupdf(pdf_path)
            if text and len(text) > 100:
                return text, "pymupdf"

        # === Level 2: pdfplumber ===
        if self._pdfplumber_available:
            text = self._extract_pdfplumber(pdf_path)
            if text and len(text) > 100:
                return text, "pdfplumber"

        # === Level 3: PaddleOCR ===
        if self._paddleocr_available:
            text = self._extract_paddleocr(pdf_path)
            if text and len(text) > 100:
                return text, "paddleocr"

        # === Level 4: Tesseract (需要PIL/Pillow) ===
        if self._tesseract_available:
            text = self._extract_tesseract(pdf_path)
            if text and len(text) > 100:
                return text, "tesseract"

        logger.error(f"所有提取方法均失败: {pdf_path}")
        return None, "all_failed"

    def _extract_pymupdf(self, pdf_path: str) -> Optional[str]:
        """Level 1: PyMuPDF提取"""
        try:
            import fitz
            doc = fitz.open(pdf_path)
            text_parts = []
            page_count = len(doc)

            for page_num in range(page_count):
                try:
                    page = doc[page_num]
                    text = page.get_text("text")
                    if text.strip():
                        text_parts.append(text)
                except Exception as page_err:
                    logger.warning(f"PyMuPDF提取第{page_num}页失败: {page_err}")
                    continue

            full_text = "\n".join(text_parts)
            logger.info(f"PyMuPDF提取成功: {len(full_text)} 字符, {page_count} 页")
            
            # 显式关闭
            try:
                doc.close()
            except:
                pass
            
            return full_text

        except Exception as e:
            logger.warning(f"PyMuPDF提取失败: {e}")
            return None

    def _extract_pdfplumber(self, pdf_path: str) -> Optional[str]:
        """Level 2: pdfplumber提取"""
        try:
            import pdfplumber

            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

            full_text = "\n".join(text_parts)
            logger.info(f"pdfplumber提取成功: {len(full_text)} 字符")
            return full_text

        except Exception as e:
            logger.warning(f"pdfplumber提取失败: {e}")
            return None

    def _extract_paddleocr(self, pdf_path: str) -> Optional[str]:
        """Level 3: PaddleOCR提取（图像型PDF）"""
        try:
            from paddleocr import PaddleOCR
            from PIL import Image
            import fitz  # 用于将PDF页面转为图像

            logger.info("使用PaddleOCR提取（可能需要较长时间）...")

            # 初始化PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False)
            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num in range(min(len(doc), 50)):  # 限制最多50页
                page = doc[page_num]
                # 渲染为图像 (150 DPI)
                mat = fitz.Matrix(150/72, 150/72)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")

                # 保存到临时文件
                tmp_img = f"/tmp/ocr_page_{page_num}.png"
                with open(tmp_img, 'wb') as f:
                    f.write(img_data)

                # OCR
                result = ocr.ocr(tmp_img, cls=True)
                if result and result[0]:
                    page_text = "\n".join([line[1][0] for line in result[0]])
                    text_parts.append(page_text)

                os.remove(tmp_img)

            doc.close()
            full_text = "\n".join(text_parts)
            logger.info(f"PaddleOCR提取成功: {len(full_text)} 字符")
            return full_text

        except Exception as e:
            logger.warning(f"PaddleOCR提取失败: {e}")
            return None

    def _extract_tesseract(self, pdf_path: str) -> Optional[str]:
        """Level 4: Tesseract提取"""
        try:
            import pytesseract
            from PIL import Image
            import fitz

            logger.info("使用Tesseract提取...")

            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num in range(min(len(doc), 30)):
                page = doc[page_num]
                mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")

                tmp_img = f"/tmp/tesseract_page_{page_num}.png"
                with open(tmp_img, 'wb') as f:
                    f.write(img_data)

                text = pytesseract.image_to_string(tmp_img, lang='chi_sim')
                if text.strip():
                    text_parts.append(text)

                os.remove(tmp_img)

            doc.close()
            full_text = "\n".join(text_parts)
            logger.info(f"Tesseract提取成功: {len(full_text)} 字符")
            return full_text

        except Exception as e:
            logger.warning(f"Tesseract提取失败: {e}")
            return None

    def extract_metadata(self, pdf_path: str) -> dict:
        """提取PDF元数据"""
        metadata = {"pages": 0, "title": "", "author": ""}

        if self._pymupdf_available:
            try:
                import fitz
                doc = fitz.open(pdf_path)
                metadata["pages"] = len(doc)
                meta = doc.metadata
                metadata["title"] = meta.get("title", "")
                metadata["author"] = meta.get("author", "")
                doc.close()
                return metadata
            except Exception:
                pass

        if self._pdfplumber_available:
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    metadata["pages"] = len(pdf.pages)
                    if pdf.metadata:
                        metadata["title"] = pdf.metadata.get("Title", "")
                        metadata["author"] = pdf.metadata.get("Author", "")
                return metadata
            except Exception:
                pass

        return metadata
