"""
SQLAlchemy database configuration and session management.
Adds persistent storage for users, conversations, and messages.
The existing RAG pipeline is unaffected by this module.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Store DB in the backend data directory alongside other persisted data
_ROOT = Path(__file__).resolve().parent.parent.parent
_DB_PATH = _ROOT / "backend" / "data" / "veritas.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DB_PATH}")

# For SQLite, connect_args is required to allow multi-thread access
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and ensures it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
