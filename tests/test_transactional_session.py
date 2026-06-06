from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from domain.models import Category
from infrastructure import database
from infrastructure.database import Base
from infrastructure.repositories import CategoryRepository


@pytest.fixture()
def isolated_session_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )
    monkeypatch.setattr(database, "SessionLocal", testing_session_local)

    try:
        yield testing_session_local
    finally:
        engine.dispose()


def test_get_session_commits_after_success(
    isolated_session_local: sessionmaker[Session],
) -> None:
    session_generator = database.get_session()
    session = next(session_generator)
    repo = CategoryRepository(session)

    category = repo.create(name="Tech", slug="tech", icon="tag")
    assert category.id

    with isolated_session_local() as verify_session:
        uncommitted = verify_session.scalars(
            select(Category).where(Category.slug == "tech")
        ).one_or_none()
        assert uncommitted is None

    with pytest.raises(StopIteration):
        next(session_generator)

    with isolated_session_local() as verify_session:
        committed = verify_session.scalars(
            select(Category).where(Category.slug == "tech")
        ).one_or_none()
        assert committed is not None


def test_get_session_rolls_back_on_error(
    isolated_session_local: sessionmaker[Session],
) -> None:
    session_generator = database.get_session()
    session = next(session_generator)
    repo = CategoryRepository(session)

    repo.create(name="Tech", slug="tech", icon="tag")

    with pytest.raises(RuntimeError):
        session_generator.throw(RuntimeError("request failed"))

    with isolated_session_local() as verify_session:
        rolled_back = verify_session.scalars(
            select(Category).where(Category.slug == "tech")
        ).one_or_none()
        assert rolled_back is None
