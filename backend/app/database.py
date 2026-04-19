from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ── Database URL ──────────────────────────────────────────────────────────────
# Production: set DATABASE_URL env var in Render to your Neon PostgreSQL URL
# Local dev:  falls back to SQLite (no setup needed)
_DATABASE_URL = os.getenv("DATABASE_URL")

if _DATABASE_URL:
    # Neon / PostgreSQL — fix legacy postgres:// scheme if present
    if _DATABASE_URL.startswith("postgres://"):
        _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URL = _DATABASE_URL
    _connect_args = {}  # PostgreSQL does not need check_same_thread
else:
    # Local SQLite fallback
    _DB_PATH = Path(__file__).resolve().parent.parent / "data" / "epichat.db"
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{_DB_PATH}"
    _connect_args = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Create all tables if they don't exist (works for both SQLite and PostgreSQL)."""
    from models.db_models import User, EEGHistory  # noqa: F401 — registers models on Base
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

