import pytest
from pathlib import Path
import fitz
from app.ingestion.pdf_parser import PDFParser

def create_sample_pdf(tmp_path: Path, filename: str, content: str) -> Path:
    pdf_path = tmp_path / filename
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), content)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path

def test_pdf_extraction_basic(tmp_path):
    sample_text = "CLINICAL FINDINGS:\nBlood Pressure: 120/80 mmHg\nHeart Rate: 72 bpm\nAssessment: Normal"
    pdf_path = create_sample_pdf(tmp_path, "sample_report.pdf", sample_text)
    
    result = PDFParser.parse_pdf(pdf_path)
    assert result.total_pages == 1
    assert "120/80" in result.full_text
    assert result.extraction_quality == "HIGH"
    assert result.ocr_required is False
    assert len(result.pages) == 1
    assert result.pages[0]["page"] == 1

def test_pdf_section_detection(tmp_path):
    text = "LABORATORY FINDINGS:\nGlucose: 95 mg/dL\nMEDICATIONS:\nLisinopril 10mg"
    pdf_path = create_sample_pdf(tmp_path, "lab_report.pdf", text)
    
    result = PDFParser.parse_pdf(pdf_path)
    assert len(result.pages[0]["sections"]) >= 1

def test_pdf_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        PDFParser.parse_pdf("nonexistent_path_file.pdf")
