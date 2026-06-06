from collections.abc import Generator
from contextlib import contextmanager

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

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager that commits or rolls back a standalone session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Generator[Session, None, None]:
    """Dependency that provides an atomic request-scoped database session."""
    with session_scope() as session:
        yield session
