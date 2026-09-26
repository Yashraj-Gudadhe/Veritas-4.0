import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import pymupdf as fitz  # PyMuPDF
from app.utils.logger import logger

class PDFIngestionResult:
    def __init__(
        self,
        document_id: str,
        filename: str,
        total_pages: int,
        pages: List[Dict[str, Any]],
        full_text: str,
        extraction_quality: str,
        text_density_score: float,
        ocr_required: bool = False
    ):
        self.document_id = document_id
        self.filename = filename
        self.total_pages = total_pages
        self.pages = pages
        self.full_text = full_text
        self.extraction_quality = extraction_quality
        self.text_density_score = text_density_score
        self.ocr_required = ocr_required

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "total_pages": self.total_pages,
            "pages": self.pages,
            "full_text": self.full_text,
            "extraction_quality": self.extraction_quality,
            "text_density_score": self.text_density_score,
            "ocr_required": self.ocr_required
        }

class PDFParser:
    """
    Robust PDF Parser with PyMuPDF (fitz) prioritizing fast native text extraction,
    per-page provenance tracking, section recognition, and deterministic OCR fallback criteria.
    """
    
    @staticmethod
    def parse_pdf(file_path: Union[str, Path], document_id: Optional[str] = None) -> PDFIngestionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found at: {path}")

        filename = path.name
        doc_id = document_id or f"DOC-{abs(hash(str(path))) % 1000000:06d}"
        
        try:
            doc = fitz.open(str(path))
        except Exception as e:
            logger.error(f"Failed to open PDF {filename}: {str(e)}")
            raise ValueError(f"Invalid or corrupted PDF file: {str(e)}")

        pages_data = []
        full_text_parts = []
        total_chars = 0
        total_pages = len(doc)
        
        for page_num in range(1, total_pages + 1):
            page = doc[page_num - 1]
            raw_text = page.get_text("text") or ""
            cleaned_text = PDFParser._clean_text(raw_text)
            
            # Extract basic structure/sections
            sections = PDFParser._detect_sections(cleaned_text)
            
            char_count = len(cleaned_text.strip())
            total_chars += char_count
            
            page_info = {
                "page": page_num,
                "document_id": doc_id,
                "source_name": filename,
                "char_count": char_count,
                "text": cleaned_text,
                "sections": sections
            }
            pages_data.append(page_info)
            if cleaned_text:
                full_text_parts.append(f"--- Page {page_num} ---\n{cleaned_text}")

        doc.close()

        full_text = "\n\n".join(full_text_parts)
        avg_chars_per_page = total_chars / max(1, total_pages)
        
        # Determine extraction quality and OCR necessity
        # If text is virtually empty (< 30 chars per page), flag for OCR fallback
        if avg_chars_per_page < 30:
            extraction_quality = "POOR_OR_SCANNED"
            ocr_required = True
            text_density_score = 0.15
        elif avg_chars_per_page < 60:
            extraction_quality = "MODERATE"
            ocr_required = False
            text_density_score = 0.65
        else:
            extraction_quality = "HIGH"
            ocr_required = False
            text_density_score = 0.95

        return PDFIngestionResult(
            document_id=doc_id,
            filename=filename,
            total_pages=total_pages,
            pages=pages_data,
            full_text=full_text,
            extraction_quality=extraction_quality,
            text_density_score=text_density_score,
            ocr_required=ocr_required
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        if not text:
            return ""
        # Remove null bytes and non-printable control characters
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        # Normalize redundant spaces while keeping line breaks
        lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
        # Remove consecutive blank lines
        cleaned_lines = []
        prev_blank = False
        for line in lines:
            if not line:
                if not prev_blank:
                    cleaned_lines.append("")
                prev_blank = True
            else:
                cleaned_lines.append(line)
                prev_blank = False
        return "\n".join(cleaned_lines).strip()

    @staticmethod
    def _detect_sections(text: str) -> List[Dict[str, Any]]:
        sections = []
        section_headers = [
            "CLINICAL FINDINGS", "LABORATORY FINDINGS", "LABORATORY REPORT", "DIAGNOSIS",
            "IMPRESSION", "ASSESSMENT", "MEDICATIONS", "PRESCRIPTION", "VITAL SIGNS",
            "HISTORY", "CHIEF COMPLAINT", "DISCHARGE SUMMARY", "RECOMMENDATIONS", "TEST RESULTS"
        ]
        
        pattern = r'(?i)^(?:[0-9\.\-\* ]*)(' + '|'.join(section_headers) + r')(?:[:\-\s]|$)'
        lines = text.splitlines()
        current_section = "General"
        current_content = []
        
        for line in lines:
            match = re.match(pattern, line.strip())
            if match:
                if current_content:
                    sections.append({
                        "name": current_section,
                        "text": "\n".join(current_content).strip()
                    })
                    current_content = []
                current_section = match.group(1).title()
            else:
                current_content.append(line)
                
        if current_content:
            sections.append({
                "name": current_section,
                "text": "\n".join(current_content).strip()
            })
            
        return sections
