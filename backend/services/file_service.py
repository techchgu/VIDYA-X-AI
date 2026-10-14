"""
VIDYA-X AI — File Service
Manages secure storage of uploaded course files, metadata extraction files,
and directory initialization. Prevents directory traversal attacks and filename collisions.
"""

import json
import os
import re
import uuid
from pathlib import Path
from typing import Dict, Any, Tuple

# Base paths relative to backend directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BACKEND_DIR / "uploads"
EXTRACTED_DIR = BACKEND_DIR / "extracted"

# Allowed course material extensions (in lowercase)
ALLOWED_EXTENSIONS = {".pdf", ".ppt", ".pptx", ".mp4"}


def ensure_directories() -> None:
    """Ensure upload and extraction storage directories exist on disk."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize an uploaded filename to prevent directory traversal and invalid characters.
    Strips directory separators, null bytes, and dangerous path sequences.
    """
    # Remove any directory paths (both unix and windows)
    clean_name = os.path.basename(filename.replace("\\", "/"))
    # Remove null bytes
    clean_name = clean_name.replace("\x00", "")
    # Remove path traversal tokens
    clean_name = re.sub(r"\.\.+", ".", clean_name)
    # Allow alphanumeric, dashes, underscores, spaces, and periods
    clean_name = re.sub(r"[^\w\s\.-]", "_", clean_name).strip()
    return clean_name or "material_file"


def generate_file_id() -> str:
    """Generate a unique, short, human-readable file ID."""
    return f"file_{uuid.uuid4().hex[:8]}"


def get_file_extension(filename: str) -> str:
    """Extract lowercase file extension including leading dot."""
    ext = os.path.splitext(filename)[1].lower()
    return ext


def save_uploaded_file(file_content: bytes, original_filename: str, file_id: str) -> Tuple[str, str]:
    """
    Save uploaded raw file bytes to the backend/uploads directory.

    Args:
        file_content: Binary content of the uploaded file.
        original_filename: The client-provided file name.
        file_id: The unique identifier generated for this file.

    Returns:
        Tuple of (clean_filename, saved_file_path).
    """
    ensure_directories()
    clean_name = sanitize_filename(original_filename)
    stored_filename = f"{file_id}_{clean_name}"
    target_path = UPLOAD_DIR / stored_filename

    # Save content to disk
    with open(target_path, "wb") as f:
        f.write(file_content)

    return clean_name, str(target_path)


def save_extraction_result(data: Dict[str, Any], file_id: str) -> str:
    """
    Save the structured extraction JSON into backend/extracted/{file_id}.json.

    Args:
        data: The structured extraction dictionary.
        file_id: Unique file identifier.

    Returns:
        The relative or absolute filename of the saved JSON extraction.
    """
    ensure_directories()
    output_filename = f"{file_id}.json"
    output_path = EXTRACTED_DIR / output_filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_filename
