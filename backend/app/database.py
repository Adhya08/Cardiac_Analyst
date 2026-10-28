"""
SQLAlchemy Database Setup
Uses SQLite for development, PostgreSQL for production.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv(override=False)

raw_db_url = os.getenv("DATABASE_URL", "sqlite:///./cardiac_data.db")
# Normalize postgres:// to postgresql:// for SQLAlchemy compatibility (Render/Supabase/Neon)
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

DATABASE_URL = raw_db_url

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {"connect_timeout": 15},
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """Create all database tables and perform light migrations if needed."""
    from .models_db import User, VitalsLog, ECGAnalysis, TriageEvent  # noqa: F401
    Base.metadata.create_all(bind=engine)
    
    # Safe schema migration for SQLite
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if "users" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("users")]
            with engine.begin() as conn:
                if "email" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
                if "hashed_password" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN hashed_password VARCHAR"))
                if "role" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'patient'"))
                if "is_active" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
                if "invite_code" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN invite_code VARCHAR"))
        if "ecg_analyses" in inspector.get_table_names():
            ecg_cols = [c["name"] for c in inspector.get_columns("ecg_analyses")]
            with engine.begin() as conn:
                if "file_data" not in ecg_cols:
                    col_type = "BYTEA" if ("postgres" in DATABASE_URL or "postgresql" in DATABASE_URL) else "BLOB"
                    conn.execute(text(f"ALTER TABLE ecg_analyses ADD COLUMN file_data {col_type}"))
    except Exception as e:
        print(f"[DB] Migration check notice: {e}")

    print("[DB] Database tables initialized.")


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Ensure tables and migrations exist
try:
    init_db()
except Exception as _e:
    print(f"[DB] Auto-init notice: {_e}")
