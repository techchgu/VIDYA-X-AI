"""
VIDYA-X AI — PDF Processor
Extracts text and image metadata page-by-page from PDF documents using PyMuPDF (fitz).
Each page forms a structured, source-traceable content unit.
"""

from typing import List, Dict, Any
import fitz  # PyMuPDF


def process_pdf(file_path: str, file_id: str, file_name: str) -> List[Dict[str, Any]]:
    """
    Process a PDF file and extract structured content units page by page.

    Args:
        file_path: Absolute path to the saved PDF file.
        file_id: Unique identifier for this uploaded file.
        file_name: Original file name.

    Returns:
        List of structured content units with preserved 1-based page numbers.

    Raises:
        ValueError: If PDF cannot be opened or is corrupted.
    """
    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        raise ValueError(f"Failed to open or parse PDF file '{file_name}': {str(exc)}")

    units: List[Dict[str, Any]] = []

    try:
        total_pages = len(doc)
        for page_idx in range(total_pages):
            page_num = page_idx + 1  # 1-based human-readable numbering
            page = doc.load_page(page_idx)

            # Extract textual content
            raw_text = page.get_text() or ""
            cleaned_text = raw_text.strip()

            # Detect images present on this page
            try:
                images = page.get_images(full=True)
                image_count = len(images)
            except Exception:
                image_count = 0

            unit_id = f"unit_{page_num:03d}"

            unit: Dict[str, Any] = {
                "unit_id": unit_id,
                "content": cleaned_text,
                "source_type": "pdf",
                "file_id": file_id,
                "file_name": file_name,
                "page": page_num,
                "slide": None,
                "timestamp_start": None,
                "timestamp_end": None,
                "metadata": {
                    "image_count": image_count,
                    "total_pages": total_pages,
                    # Structured for future multimodal/vision expansion in Steps 4 & 5
                    "visual_content": None,
                },
            }
            units.append(unit)
    finally:
        doc.close()

    return units
