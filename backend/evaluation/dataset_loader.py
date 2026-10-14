"""
VIDYA-X AI — Dataset Loader Service (Step 13)

Parses, validates, and loads versioned evaluation benchmark dataset cases (.jsonl files)
and dataset manifest metadata.
"""

import json
import os
import logging
from typing import Dict, Any, List, Optional

from evaluation.config import DATASETS_DIR, DEFAULT_DATASET_VERSION
from evaluation.schemas import DatasetCase

logger = logging.getLogger(__name__)


def load_manifest(datasets_dir: Optional[str] = None) -> Dict[str, Any]:
    """Load dataset manifest metadata."""
    if not datasets_dir:
        datasets_dir = DATASETS_DIR
    manifest_path = os.path.join(datasets_dir, "dataset_manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Dataset manifest not found at: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_case_dict(case_dict: Dict[str, Any]) -> bool:
    """Validate that a dataset case dictionary has all required schema fields."""
    required = ["case_id", "dataset_version", "task_type", "course_id"]
    for field in required:
        if field not in case_dict or not case_dict[field]:
            logger.error(f"Case validation failed: missing field '{field}' in {case_dict}")
            return False
    return True


def load_dataset_cases(
    task_type: Optional[str] = None,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    datasets_dir: Optional[str] = None,
    max_cases: Optional[int] = None,
) -> List[DatasetCase]:
    """
    Load dataset cases from JSONL files in datasets_dir.
    Filters by task_type and dataset_version if specified.
    """
    if not datasets_dir:
        datasets_dir = DATASETS_DIR

    file_names = [
        "retrieval_cases.jsonl",
        "rag_cases.jsonl",
        "citation_cases.jsonl",
        "quiz_cases.jsonl",
        "personalization_cases.jsonl",
        "study_plan_cases.jsonl",
    ]

    loaded_cases = []

    for fname in file_names:
        fpath = os.path.join(datasets_dir, fname)
        if not os.path.exists(fpath):
            continue

        with open(fpath, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                    if not validate_case_dict(data):
                        continue

                    if dataset_version and data.get("dataset_version") != dataset_version:
                        continue

                    if task_type and data.get("task_type") != task_type:
                        continue

                    case_obj = DatasetCase(**data)
                    loaded_cases.append(case_obj)

                    if max_cases and len(loaded_cases) >= max_cases:
                        break

                except Exception as exc:
                    logger.warning(f"Error parsing case at {fname}:{line_no}: {exc}")

        if max_cases and len(loaded_cases) >= max_cases:
            break

    return loaded_cases
