"""
VIDYA-X AI - Database Package
Exposes engine, SessionLocal, models, and initialization logic.
"""

from .connection import engine, SessionLocal, get_db, Base
from .models import (
    Course,
    Material,
    ContentUnit,
    Topic,
    Concept,
    Definition,
    Relationship,
    Prerequisite,
    KnowledgeChunk,
    EMBEDDING_DIMENSION,
)
from .init_db import init_db

__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "Base",
    "init_db",
    "Course",
    "Material",
    "ContentUnit",
    "Topic",
    "Concept",
    "Definition",
    "Relationship",
    "Prerequisite",
    "KnowledgeChunk",
    "EMBEDDING_DIMENSION",
]
