"""
VIDYA-X AI — Unit & Integration Test for Content Processors
Verifies PDF, PPTX, and API extraction behavior against Step 3 requirements.
"""

import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from processors import process_pdf, process_ppt
from services import (
    ensure_directories,
    sanitize_filename,
    save_uploaded_file,
    save_extraction_result,
    ALLOWED_EXTENSIONS,
)


def test_filename_sanitization():
    print("Testing filename sanitization...")
    bad_name = "../../etc/passwd..\\..\\malicious_file?.pdf"
    clean = sanitize_filename(bad_name)
    assert ".." not in clean, f"Path traversal not removed: {clean}"
    assert "/" not in clean and "\\" not in clean, f"Slashes not removed: {clean}"
    print(f"  [OK] Cleaned '{bad_name}' -> '{clean}'")


def test_pdf_processing():
    print("Testing PDF processing...")
    import fitz

    ensure_directories()
    sample_pdf_path = Path(__file__).parent / "uploads" / "sample_test.pdf"

    # Create a small 2-page test PDF
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 50), "Newton's First Law: An object at rest stays at rest.", fontsize=12)

    page2 = doc.new_page()
    page2.insert_text((50, 50), "Newton's Second Law: F = m * a.", fontsize=12)
    doc.save(str(sample_pdf_path))
    doc.close()

    # Process PDF
    units = process_pdf(str(sample_pdf_path), "test_pdf_01", "sample_test.pdf")
    assert len(units) == 2, f"Expected 2 units, got {len(units)}"
    assert units[0]["page"] == 1, "Page 1 index mismatch"
    assert units[1]["page"] == 2, "Page 2 index mismatch"
    assert "Newton's First Law" in units[0]["content"], "Page 1 content missing"
    assert "Newton's Second Law" in units[1]["content"], "Page 2 content missing"
    assert units[0]["source_type"] == "pdf", "Source type should be pdf"
    assert units[0]["slide"] is None, "Slide should be None for PDF"
    assert units[0]["timestamp_start"] is None, "Timestamp should be None for PDF"

    # Save extraction JSON
    save_extraction_result({"file_id": "test_pdf_01", "units": units}, "test_pdf_01")
    ext_file = Path(__file__).parent / "extracted" / "test_pdf_01.json"
    assert ext_file.exists(), "Extracted JSON was not created"
    print(f"  [OK] PDF processed successfully: {len(units)} pages extracted with 1-based page indices.")


def test_pptx_processing():
    print("Testing PPTX processing...")
    from pptx import Presentation

    ensure_directories()
    sample_pptx_path = Path(__file__).parent / "uploads" / "sample_test.pptx"

    prs = Presentation()
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])
    slide1.shapes.title.text = "Introduction to Physics"
    slide1.placeholders[1].text = "Chapter 1: Kinematics and Dynamics"

    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Newton's Laws"
    slide2.placeholders[1].text = "Third Law: For every action there is an equal and opposite reaction."

    prs.save(str(sample_pptx_path))

    units = process_ppt(str(sample_pptx_path), "test_ppt_01", "sample_test.pptx")
    assert len(units) == 2, f"Expected 2 slides, got {len(units)}"
    assert units[0]["slide"] == 1, "Slide 1 index mismatch"
    assert units[1]["slide"] == 2, "Slide 2 index mismatch"
    assert "Introduction to Physics" in units[0]["content"], "Slide 1 title missing"
    assert "Newton's Laws" in units[1]["content"], "Slide 2 title missing"
    assert units[0]["source_type"] == "ppt", "Source type should be ppt"
    assert units[0]["page"] is None, "Page should be None for PPT"

    save_extraction_result({"file_id": "test_ppt_01", "units": units}, "test_ppt_01")
    ext_file = Path(__file__).parent / "extracted" / "test_ppt_01.json"
    assert ext_file.exists(), "Extracted JSON was not created"
    print(f"  [OK] PPTX processed successfully: {len(units)} slides extracted with 1-based slide indices.")


if __name__ == "__main__":
    print("=== Running VIDYA-X AI Extraction Tests ===")
    test_filename_sanitization()
    test_pdf_processing()
    test_pptx_processing()
    print("=== ALL TESTS PASSED SUCCESSFULLY! ===")
