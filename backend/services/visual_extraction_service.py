"""
VIDYA-X AI — Visual Extraction Service (Step 14)
Coordinates image extraction from PDF, PPTX, and lecture-video files.
Supports deduplication, resizing, page-rendering fallbacks, and bounded frame sampling.
"""

import hashlib
import io
import logging
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
VISUAL_ASSETS_DIR = BACKEND_DIR / "visual_assets"

# Configurable extraction bounds
MAX_IMAGES_PER_DOCUMENT = int(os.getenv("VISION_MAX_IMAGES_PER_DOC", "40"))
MAX_FRAMES_PER_VIDEO = int(os.getenv("VISION_MAX_FRAMES_PER_VIDEO", "15"))
FRAME_INTERVAL_SECONDS = int(os.getenv("VISION_FRAME_INTERVAL_SECONDS", "30"))
MAX_IMAGE_DIMENSION = int(os.getenv("VISION_MAX_IMAGE_DIMENSION", "1024"))
MIN_IMAGE_BYTES = int(os.getenv("VISION_MIN_IMAGE_BYTES", "1024"))  # Filter out tiny icon artifacts


def ensure_visual_assets_dir() -> Path:
    """Ensure root storage directory for extracted visual artifacts exists."""
    VISUAL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    return VISUAL_ASSETS_DIR


def compute_fingerprint(image_bytes: bytes) -> str:
    """Compute SHA-256 fingerprint for deduplication."""
    return hashlib.sha256(image_bytes).hexdigest()


def save_image_bytes(image_bytes: bytes, material_id: str, asset_id: str, ext: str = ".jpg") -> str:
    """Save raw visual image to managed backend/visual_assets/{material_id}/ storage."""
    ensure_visual_assets_dir()
    mat_dir = VISUAL_ASSETS_DIR / material_id
    mat_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{asset_id}{ext}"
    target = mat_dir / filename
    target.write_bytes(image_bytes)
    return str(target)


def resize_image_if_needed(image_bytes: bytes, max_dim: int = MAX_IMAGE_DIMENSION) -> bytes:
    """Downscale large images proportionally to limit memory and token consumption."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        if max(w, h) <= max_dim:
            # If already converted or in reasonable range, re-encode clean jpeg if needed
            if img.format != "JPEG":
                rgb = img.convert("RGB")
                buf = io.BytesIO()
                rgb.save(buf, format="JPEG", quality=85)
                return buf.getvalue()
            return image_bytes

        scale = max_dim / float(max(w, h))
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        resized = img.resize(new_size, Image.Resampling.LANCZOS).convert("RGB")
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as exc:
        logger.debug(f"Image resize skipped/failed: {exc}")
        return image_bytes


def extract_images_from_pdf(
    file_path: str,
    material_id: str,
    file_name: str,
    seen_fingerprints: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract embedded figures and render diagrammatic pages from PDF via PyMuPDF.
    """
    import fitz
    seen = seen_fingerprints or set()
    records: List[Dict[str, Any]] = []
    count = 0

    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        logger.error(f"Failed to open PDF '{file_path}': {exc}")
        return records

    try:
        for page_idx in range(len(doc)):
            if count >= MAX_IMAGES_PER_DOCUMENT:
                break
            page_num = page_idx + 1
            page = doc.load_page(page_idx)

            page_had_embedded = False
            try:
                images = page.get_images(full=True)
                for img_info in images:
                    if count >= MAX_IMAGES_PER_DOCUMENT:
                        break
                    xref = img_info[0]
                    try:
                        base_img = doc.extract_image(xref)
                        raw_bytes = base_img.get("image", b"")
                        img_ext = f".{base_img.get('ext', 'jpg').lower()}"
                    except Exception:
                        continue

                    if len(raw_bytes) < MIN_IMAGE_BYTES:
                        continue

                    fp = compute_fingerprint(raw_bytes)
                    if fp in seen:
                        continue
                    seen.add(fp)

                    processed_bytes = resize_image_if_needed(raw_bytes)
                    asset_id = f"va_{uuid.uuid4().hex[:12]}"
                    saved_path = save_image_bytes(processed_bytes, material_id, asset_id, ".jpg")

                    records.append({
                        "asset_id": asset_id,
                        "asset_type": "embedded_image",
                        "page_number": page_num,
                        "slide_number": None,
                        "timestamp_start": None,
                        "timestamp_end": None,
                        "image_bytes": processed_bytes,
                        "image_path": saved_path,
                        "content_fingerprint": fp,
                        "source_type": "pdf",
                        "file_name": file_name,
                    })
                    page_had_embedded = True
                    count += 1
            except Exception as exc:
                logger.warning(f"Error scanning embedded images on page {page_num}: {exc}")

            # If the page contains graphical illustrations/charts without raw embedded bitmaps,
            # or if it has low text and high graphical drawing elements, render page image.
            # We render up to a fraction of pages to avoid massive overhead.
            drawings = page.get_drawings()
            if not page_had_embedded and len(drawings) > 5 and count < MAX_IMAGES_PER_DOCUMENT:
                try:
                    mat = fitz.Matrix(1.5, 1.5)
                    pix = page.get_pixmap(matrix=mat)
                    render_bytes = pix.tobytes("jpeg")
                    if len(render_bytes) >= MIN_IMAGE_BYTES:
                        fp = compute_fingerprint(render_bytes)
                        if fp not in seen:
                            seen.add(fp)
                            processed_bytes = resize_image_if_needed(render_bytes)
                            asset_id = f"va_{uuid.uuid4().hex[:12]}"
                            saved_path = save_image_bytes(processed_bytes, material_id, asset_id, ".jpg")

                            records.append({
                                "asset_id": asset_id,
                                "asset_type": "rendered_pdf_page",
                                "page_number": page_num,
                                "slide_number": None,
                                "timestamp_start": None,
                                "timestamp_end": None,
                                "image_bytes": processed_bytes,
                                "image_path": saved_path,
                                "content_fingerprint": fp,
                                "source_type": "pdf",
                                "file_name": file_name,
                            })
                            count += 1
                except Exception as exc:
                    logger.warning(f"Error rendering page {page_num}: {exc}")
    finally:
        doc.close()

    return records


def extract_images_from_pptx(
    file_path: str,
    material_id: str,
    file_name: str,
    seen_fingerprints: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract embedded images and diagrams from PPTX presentation slides.
    """
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    seen = seen_fingerprints or set()
    records: List[Dict[str, Any]] = []
    count = 0

    try:
        prs = Presentation(file_path)
    except Exception as exc:
        logger.error(f"Failed to open PPTX '{file_path}': {exc}")
        return records

    for slide_idx, slide in enumerate(prs.slides):
        if count >= MAX_IMAGES_PER_DOCUMENT:
            break
        slide_num = slide_idx + 1

        for shape in slide.shapes:
            if count >= MAX_IMAGES_PER_DOCUMENT:
                break
            raw_bytes = None
            try:
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE and hasattr(shape, "image"):
                    raw_bytes = shape.image.blob
                elif hasattr(shape, "image"):
                    raw_bytes = shape.image.blob
            except Exception:
                continue

            if not raw_bytes or len(raw_bytes) < MIN_IMAGE_BYTES:
                continue

            fp = compute_fingerprint(raw_bytes)
            if fp in seen:
                continue
            seen.add(fp)

            processed_bytes = resize_image_if_needed(raw_bytes)
            asset_id = f"va_{uuid.uuid4().hex[:12]}"
            saved_path = save_image_bytes(processed_bytes, material_id, asset_id, ".jpg")

            records.append({
                "asset_id": asset_id,
                "asset_type": "embedded_image",
                "page_number": None,
                "slide_number": slide_num,
                "timestamp_start": None,
                "timestamp_end": None,
                "image_bytes": processed_bytes,
                "image_path": saved_path,
                "content_fingerprint": fp,
                "source_type": "ppt",
                "file_name": file_name,
            })
            count += 1

    return records


def extract_frames_from_video(
    file_path: str,
    material_id: str,
    file_name: str,
    seen_fingerprints: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract educational keyframes from video file using FFmpeg at configured intervals.
    """
    seen = seen_fingerprints or set()
    records: List[Dict[str, Any]] = []

    if not shutil.which("ffmpeg"):
        logger.warning("FFmpeg binary not detected in PATH; skipping video frame sampling.")
        return records

    duration = _get_video_duration(file_path)
    if duration is None or duration <= 0:
        logger.warning(f"Could not determine duration for video: {file_name}")
        return records

    interval = max(FRAME_INTERVAL_SECONDS, 10)
    sample_points: List[float] = []
    t = float(interval)
    while t < duration and len(sample_points) < MAX_FRAMES_PER_VIDEO:
        sample_points.append(t)
        t += interval

    mat_dir = ensure_visual_assets_dir() / material_id
    mat_dir.mkdir(parents=True, exist_ok=True)

    for ts in sample_points:
        asset_id = f"va_{uuid.uuid4().hex[:12]}"
        out_path = mat_dir / f"{asset_id}.jpg"

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(ts),
            "-i", file_path,
            "-vframes", "1",
            "-q:v", "3",
            "-vf", f"scale='min({MAX_IMAGE_DIMENSION},iw)':-1",
            str(out_path),
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
            if res.returncode != 0 or not out_path.exists():
                continue
            raw_bytes = out_path.read_bytes()
        except Exception as exc:
            logger.warning(f"FFmpeg frame extraction failed at {ts}s: {exc}")
            continue

        if len(raw_bytes) < MIN_IMAGE_BYTES:
            if out_path.exists():
                out_path.unlink()
            continue

        fp = compute_fingerprint(raw_bytes)
        if fp in seen:
            if out_path.exists():
                out_path.unlink()
            continue
        seen.add(fp)

        ts_start_str = _format_timestamp(ts)
        ts_end_str = _format_timestamp(min(ts + interval, duration))

        records.append({
            "asset_id": asset_id,
            "asset_type": "video_frame",
            "page_number": None,
            "slide_number": None,
            "timestamp_start": ts_start_str,
            "timestamp_end": ts_end_str,
            "image_bytes": raw_bytes,
            "image_path": str(out_path),
            "content_fingerprint": fp,
            "source_type": "video",
            "file_name": file_name,
        })

    return records


def _get_video_duration(file_path: str) -> Optional[float]:
    """Retrieve video duration using ffprobe."""
    if not shutil.which("ffprobe"):
        return None
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        return float(proc.stdout.strip())
    except Exception:
        return None


def _format_timestamp(seconds: float) -> str:
    s = max(0.0, float(seconds))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"
