"""
VIDYA-X AI — Visual Indexing Service (Step 14)
Orchestrates extracting visual assets, generating vision descriptions, embedding them into
the existing knowledge chunk infrastructure, and maintaining processing status.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from database.models import KnowledgeChunk, Material, VisualAsset
from services.embedding_service import generate_embedding
from services.vision_service import analyze_image, vision_available
from services.visual_extraction_service import (
    extract_images_from_pdf,
    extract_images_from_pptx,
    extract_frames_from_video,
)

logger = logging.getLogger(__name__)


def process_material_visuals(
    db: Session,
    material_id: str,
    skip_vision: bool = False,
) -> Dict[str, Any]:
    """
    Run full visual processing pipeline for a specific Material:
      1. Extract raw images / rendered pages / video frames
      2. Analyze via Vision Model (if available & not skipped) or construct detailed structural metadata
      3. Index plain-text visual descriptions into KnowledgeChunk table with is_visual=True
      4. Persist VisualAsset records linked to KnowledgeChunk
    """
    material = db.get(Material, material_id)
    if not material:
        return {"success": False, "error": f"Material '{material_id}' not found."}

    if not material.file_path:
        return {"success": False, "error": f"Material '{material_id}' has no stored physical file."}

    course_id = material.course_id
    file_path = material.file_path
    file_name = material.file_name
    source_type = material.source_type

    stats = {
        "material_id": material_id,
        "course_id": course_id,
        "file_name": file_name,
        "source_type": source_type,
        "images_discovered": 0,
        "images_processed": 0,
        "images_failed": 0,
        "chunks_created": 0,
        "success": True,
    }

    # Fetch existing fingerprints for this material to prevent duplicate re-extraction
    existing_fingerprints = {
        row[0]
        for row in db.query(VisualAsset.content_fingerprint)
        .filter(
            VisualAsset.material_id == material_id,
            VisualAsset.content_fingerprint.isnot(None),
        )
        .all()
        if row[0]
    }

    # 1. Image extraction
    try:
        if source_type == "pdf":
            raw_items = extract_images_from_pdf(file_path, material_id, file_name, existing_fingerprints)
        elif source_type == "ppt":
            raw_items = extract_images_from_pptx(file_path, material_id, file_name, existing_fingerprints)
        elif source_type == "video":
            raw_items = extract_frames_from_video(file_path, material_id, file_name, existing_fingerprints)
        else:
            return {"success": False, "error": f"Unsupported source type '{source_type}' for visual processing."}
    except Exception as exc:
        logger.error(f"Visual extraction error for {material_id}: {exc}")
        return {"success": False, "error": f"Extraction failed: {exc}"}

    stats["images_discovered"] = len(raw_items)
    if not raw_items:
        return {**stats, "message": "No new visual assets found in material."}

    use_vision = (not skip_vision) and vision_available()

    # 2. Process each visual item
    for item in raw_items:
        asset_id = item["asset_id"]
        fp = item["content_fingerprint"]
        img_bytes = item.pop("image_bytes", b"")

        va = db.get(VisualAsset, asset_id)
        if not va:
            va = VisualAsset(
                id=asset_id,
                course_id=course_id,
                material_id=material_id,
                source_file_name=file_name,
                source_type=item["source_type"],
                asset_type=item["asset_type"],
                page_number=item.get("page_number"),
                slide_number=item.get("slide_number"),
                timestamp_start=item.get("timestamp_start"),
                timestamp_end=item.get("timestamp_end"),
                image_path=item.get("image_path"),
                content_fingerprint=fp,
                processing_status="processing",
            )
            db.add(va)
            db.flush()

        description_text = ""
        structured_data = None

        if use_vision and img_bytes:
            try:
                analysis = analyze_image(
                    image_bytes=img_bytes,
                    context_text=f"Extracted from {file_name} ({item['source_type']})",
                    page=item.get("page_number"),
                    slide=item.get("slide_number"),
                    timestamp_start=item.get("timestamp_start"),
                    timestamp_end=item.get("timestamp_end"),
                )
                description_text = analysis["visual_description"]
                structured_data = analysis["structured_description"]

                # Refine asset_type from vision output if valid category
                model_asset_type = structured_data.get("asset_type")
                if model_asset_type in {
                    "diagram", "chart", "equation", "table", "flowchart",
                    "scientific_illustration", "annotated_image", "process_diagram", "slide"
                }:
                    va.asset_type = model_asset_type

                va.visual_description = description_text
                va.structured_description = structured_data
                va.processing_status = "completed"
                stats["images_processed"] += 1
            except Exception as exc:
                logger.warning(f"Vision inference failed for asset {asset_id}: {exc}")
                va.processing_status = "failed"
                va.processing_error = str(exc)[:400]
                stats["images_failed"] += 1
                db.flush()
                continue
        else:
            # Deterministic descriptor fallback when offline or skip_vision requested
            loc_label = []
            if item.get("page_number"):
                loc_label.append(f"Page {item['page_number']}")
            if item.get("slide_number"):
                loc_label.append(f"Slide {item['slide_number']}")
            if item.get("timestamp_start"):
                loc_label.append(f"Timestamp {item['timestamp_start']}")
            loc_str = ", ".join(loc_label) or "Course document"

            clean_asset_name = item["asset_type"].replace("_", " ").title()
            description_text = (
                f"Visual content: {clean_asset_name} from {file_name} at {loc_str}. "
                f"Course study illustration indexed for visual reference."
            )
            structured_data = {
                "asset_type": item["asset_type"],
                "title": f"{clean_asset_name} - {loc_str}",
                "summary": description_text,
                "labels": [],
                "relationships": [],
                "equations": [],
                "chart_data": None,
                "uncertain_regions": [],
                "source_location": {
                    "page": item.get("page_number"),
                    "slide": item.get("slide_number"),
                    "timestamp_start": item.get("timestamp_start"),
                    "timestamp_end": item.get("timestamp_end"),
                },
            }
            va.visual_description = description_text
            va.structured_description = structured_data
            va.processing_status = "completed"
            stats["images_processed"] += 1

        # 3. Create or update KnowledgeChunk with vector embedding
        if description_text.strip():
            chunk_id = f"chunk_visual_{asset_id}"
            chunk_meta = {
                "file_name": file_name,
                "source_type": item["source_type"],
                "page": item.get("page_number"),
                "slide": item.get("slide_number"),
                "timestamp_start": item.get("timestamp_start"),
                "timestamp_end": item.get("timestamp_end"),
                "visual_asset_id": asset_id,
                "asset_type": va.asset_type,
                "is_visual": True,
            }

            emb = generate_embedding(description_text)
            k_chunk = db.get(KnowledgeChunk, chunk_id)
            if not k_chunk:
                k_chunk = KnowledgeChunk(
                    id=chunk_id,
                    course_id=course_id,
                    material_id=material_id,
                    content_unit_id=None,
                    content=description_text,
                    chunk_type="visual_description",
                    embedding=emb,
                    chunk_metadata=chunk_meta,
                )
                db.add(k_chunk)
                stats["chunks_created"] += 1
            else:
                k_chunk.content = description_text
                k_chunk.embedding = emb
                k_chunk.chunk_metadata = chunk_meta

            va.knowledge_chunk_id = chunk_id

        db.flush()

    db.commit()
    return stats


def get_material_visual_status(db: Session, material_id: str) -> Dict[str, Any]:
    """Retrieve visual asset status summary for a specific course material."""
    total = db.query(VisualAsset).filter(VisualAsset.material_id == material_id).count()
    completed = db.query(VisualAsset).filter(
        VisualAsset.material_id == material_id,
        VisualAsset.processing_status == "completed",
    ).count()
    failed = db.query(VisualAsset).filter(
        VisualAsset.material_id == material_id,
        VisualAsset.processing_status == "failed",
    ).count()
    pending = db.query(VisualAsset).filter(
        VisualAsset.material_id == material_id,
        VisualAsset.processing_status.in_(["pending", "processing"]),
    ).count()

    overall = "none"
    if total > 0:
        if pending > 0:
            overall = "processing"
        elif completed == total:
            overall = "completed"
        elif completed > 0:
            overall = "partial"
        else:
            overall = "failed"

    return {
        "material_id": material_id,
        "total_assets": total,
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "overall_status": overall,
    }
