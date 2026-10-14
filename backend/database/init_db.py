"""
VIDYA-X AI — Database Initializer (Step 5)
Initializes PostgreSQL database, enables the pgvector extension, and creates all tables.
Can be executed directly: python -m database.init_db
"""

import sys
from pathlib import Path
from sqlalchemy import text

# Ensure backend directory is in path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from database.connection import engine, Base, is_sqlite
from database.models import (
    Course,
    Material,
    ContentUnit,
    Topic,
    Concept,
    Definition,
    Relationship,
    Prerequisite,
    KnowledgeChunk,
)


def init_db() -> bool:
    """
    Initialize database tables and enable pgvector extension.
    Returns True if successful, False otherwise.
    """
    try:
        with engine.connect() as connection:
            if not is_sqlite:
                print("Enabling pgvector extension on PostgreSQL...")
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                connection.commit()
                print("  [OK] pgvector extension ready.")

            print("Creating database tables from SQLAlchemy metadata...")
            Base.metadata.create_all(bind=connection)
            connection.commit()
            print("  [OK] All tables successfully created.")
            return True

    except Exception as exc:
        print(f"Database initialization note: {str(exc)}")
        print("Tip: Ensure PostgreSQL is running and DATABASE_URL is configured in backend/.env")
        return False


if __name__ == "__main__":
    print("=== Initializing VIDYA-X AI Database ===")
    success = init_db()
    if success:
        print("=== Database initialization finished successfully ===")
    else:
        sys.exit(1)
