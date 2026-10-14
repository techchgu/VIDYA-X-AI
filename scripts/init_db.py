"""
VIDYA-X AI — Production Database Initialization & Extension Setup (Step 16)
Connects to target PostgreSQL database, enables pgvector extension, and creates schema idempotently.
Can also initialize SQLite fallback environments.
"""

import sys
import os
import logging
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("db_init")

# Load backend/.env
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:password@localhost:5432/vidya_x")


def init_database(db_url: str = DATABASE_URL) -> bool:
    """
    Idempotent database initialization:
      1. Connects to database.
      2. If PostgreSQL, runs `CREATE EXTENSION IF NOT EXISTS vector;`
      3. Creates all SQLAlchemy models in database.models.
    """
    logger.info(f"Target Database URL: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    is_sqlite = db_url.startswith("sqlite")

    engine_kwargs = {}
    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_pre_ping"] = True

    try:
        engine = create_engine(db_url, **engine_kwargs)
        with engine.connect() as conn:
            logger.info("Successfully established connection to database.")

            if not is_sqlite:
                logger.info("Checking & enabling pgvector extension ('CREATE EXTENSION IF NOT EXISTS vector;')...")
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
                logger.info("pgvector extension ready.")

        # Import models and Base
        from database.connection import Base
        import database.models  # Registers all models

        logger.info("Creating tables from SQLAlchemy metadata...")
        Base.metadata.create_all(engine)
        logger.info("Database schema initialized successfully.")
        return True

    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")
        return False


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DATABASE_URL
    success = init_database(url)
    sys.exit(0 if success else 1)
