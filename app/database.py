from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


def _normalize_url(url: str) -> str:
    """Railway/Heroku hand out `postgres://...`; SQLAlchemy + psycopg3 wants
    the `postgresql+psycopg://` driver prefix."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _normalize_url(settings.database_url)
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (register models on Base)

    Base.metadata.create_all(bind=engine)
    # Lightweight migrations for columns added to existing tables (create_all
    # only creates new tables, it never alters an existing one).
    _ensure_column("users", "resting_bmr", default="0")


def _ensure_column(table: str, column: str, default: str) -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns(table)}
    if column in existing:
        return
    col_type = "REAL" if engine.dialect.name == "sqlite" else "DOUBLE PRECISION"
    with engine.begin() as conn:
        conn.execute(
            text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}")
        )
