"""
VIDYA-X AI — PPT/PPTX Processor
Extracts slide text, shapes, notes, and image counts from PowerPoint presentations using python-pptx.
Each slide forms a structured, source-traceable content unit with 1-based slide numbering.
"""

from typing import List, Dict, Any
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def process_ppt(file_path: str, file_id: str, file_name: str) -> List[Dict[str, Any]]:
    """
    Process a PowerPoint (.ppt / .pptx) file and extract structured content units slide by slide.

    Args:
        file_path: Absolute path to the saved presentation file.
        file_id: Unique identifier for this uploaded file.
        file_name: Original file name.

    Returns:
        List of structured content units with preserved 1-based slide numbers.

    Raises:
        ValueError: If presentation cannot be opened or is corrupted.
    """
    try:
        prs = Presentation(file_path)
    except Exception as exc:
        raise ValueError(f"Failed to open or parse PowerPoint file '{file_name}': {str(exc)}")

    units: List[Dict[str, Any]] = []
    total_slides = len(prs.slides)

    for slide_idx, slide in enumerate(prs.slides):
        slide_num = slide_idx + 1  # 1-based numbering

        text_pieces: List[str] = []
        image_count = 0

        # Inspect all shapes on this slide
        for shape in slide.shapes:
            # 1. Check for text inside text frames / shapes
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text_line = paragraph.text.strip()
                    if text_line:
                        text_pieces.append(text_line)

            # 2. Check for text inside tables
            elif shape.has_table:
                for row in shape.table.rows:
                    row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_texts:
                        text_pieces.append(" | ".join(row_texts))

            # 3. Detect images / pictures
            try:
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    image_count += 1
                elif hasattr(shape, "image"):
                    image_count += 1
            except Exception:
                pass

        # Also extract speaker notes if present
        notes_text = ""
        try:
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            notes_text = ""

        combined_content = "\n".join(text_pieces)
        if notes_text:
            combined_content += (f"\n\n[Speaker Notes]\n{notes_text}" if combined_content else f"[Speaker Notes]\n{notes_text}")

        unit_id = f"unit_{slide_num:03d}"

        unit: Dict[str, Any] = {
            "unit_id": unit_id,
            "content": combined_content,
            "source_type": "ppt",
            "file_id": file_id,
            "file_name": file_name,
            "page": None,
            "slide": slide_num,
            "timestamp_start": None,
            "timestamp_end": None,
            "metadata": {
                "image_count": image_count,
                "total_slides": total_slides,
                "has_notes": bool(notes_text),
                # Structured for future multimodal/vision expansion in Steps 4 & 5
                "visual_content": None,
            },
        }
        units.append(unit)

    return units
