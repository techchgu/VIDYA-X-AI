"""
VIDYA-X AI — Centralized Production Configuration (Step 16)
Validates and exposes typed, environment-driven settings with sensible defaults.
Guarantees secret credentials are never exposed to clients or logged.
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Base paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
ENV_PATH = BACKEND_DIR / ".env"

# Load local environment if present
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
elif (ROOT_DIR / ".env").exists():
    load_dotenv(dotenv_path=ROOT_DIR / ".env")


class Settings:
    # Application Mode
    APP_ENV: str = os.getenv("APP_ENV", "development").lower()
    DEBUG: bool = APP_ENV == "development"
    VERSION: str = "1.0.0"

    # Server Bind
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # CORS Allowed Origins
    _raw_origins = os.getenv("FRONTEND_ORIGINS", "")
    if _raw_origins and _raw_origins.strip() != "*":
        CORS_ORIGINS: List[str] = [orig.strip() for orig in _raw_origins.split(",") if orig.strip()]
    elif APP_ENV == "production":
        # Safe default origins for production if unspecified
        CORS_ORIGINS: List[str] = [
            "http://localhost:3000",
            "http://localhost:8000",
            "https://vidya-x.vercel.app",
            "https://vidya-x.onrender.com",
        ]
    else:
        # Development fallback allows local dev origins
        CORS_ORIGINS: List[str] = ["*"]

    # Database
    DEFAULT_DB = "postgresql+psycopg://postgres:password@localhost:5432/vidya_x"
    DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_DB)

    # Storage Paths
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(BACKEND_DIR / "uploads")))
    VISUAL_ASSETS_DIR: Path = Path(os.getenv("VISUAL_ASSETS_DIR", str(BACKEND_DIR / "visual_assets")))
    EXTRACTED_DIR: Path = Path(os.getenv("EXTRACTED_DIR", str(BACKEND_DIR / "extracted")))
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))

    # Embeddings
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))

    # Vision & LLM Providers
    VISION_MODEL: str = os.getenv("VISION_MODEL", "gemini-1.5-flash")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-1.5-flash")
    HAS_GEMINI_KEY: bool = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    # Demo Mode
    DEMO_MODE_ENABLED: bool = os.getenv("DEMO_MODE_ENABLED", "true").lower() in ("true", "1", "yes")

    @classmethod
    def ensure_storage_directories(cls):
        """Create storage roots if missing."""
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        cls.VISUAL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        cls.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)


config = Settings()
