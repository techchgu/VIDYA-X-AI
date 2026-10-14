"""
VIDYA-X AI — Database Connection & Session Management (Step 5)
Configures SQLAlchemy engine, session factory, and dependency injection for PostgreSQL + pgvector.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load environment variables from backend/.env if present
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Default to PostgreSQL with psycopg driver
DEFAULT_DB_URL = "postgresql+psycopg://postgres:password@localhost:5432/vidya_x"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# Fallback mechanism: allow SQLite in-memory or file for automated test suites
# when a live PostgreSQL instance is not available
is_sqlite = DATABASE_URL.startswith("sqlite")

engine_kwargs = {}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["connect_args"] = {"connect_timeout": 3}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
