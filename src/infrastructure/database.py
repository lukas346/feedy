from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from infrastructure.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


DATABASE_URL = settings.database_url

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency that provides a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
