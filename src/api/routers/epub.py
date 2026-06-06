"""EPUB export router."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from application.services.epub import (
    EPUBGenerationError,
    EPUB_MAX_ARTICLES,
    epub_service,
)
from i18n import create_t_function
from infrastructure.database import get_session
from infrastructure.repositories import ArticleRepository

router = APIRouter(prefix="/api/epub", tags=["epub"])


class EPUBExportRequest(BaseModel):
    """Request body for EPUB export."""

    article_ids: list[str] = Field(default_factory=list)


def _unique_article_ids(article_ids: list[str]) -> list[str]:
    """Deduplicate article IDs while preserving the selection order."""
    seen: set[str] = set()
    unique_ids: list[str] = []
    for article_id in article_ids:
        if article_id in seen:
            continue
        seen.add(article_id)
        unique_ids.append(article_id)
    return unique_ids


def _epub_download_filename() -> str:
    """Build an EPUB download filename using the local date."""
    return f"feedy-{date.today().isoformat()}.epub"


@router.post("/export")
def export_epub(
    request: Request,
    export_request: EPUBExportRequest,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    """Export selected articles as an EPUB file."""
    lang = getattr(request.state, "lang", "en")
    t = create_t_function(lang)
    article_ids = _unique_article_ids(export_request.article_ids)

    if not article_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("epub.no_selection"),
        )
    if len(article_ids) > EPUB_MAX_ARTICLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("epub.too_many_articles", count=str(EPUB_MAX_ARTICLES)),
        )

    article_repo = ArticleRepository(session)
    articles = article_repo.get_by_ids(article_ids)
    if len(articles) != len(article_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("epub.articles_not_found"),
        )

    try:
        epub_bytes = epub_service.generate(
            articles,
            title=t("epub.book_title"),
        )
    except EPUBGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    article_repo.mark_as_read_by_ids(article_ids)

    return Response(
        content=epub_bytes,
        media_type="application/epub+zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename={_epub_download_filename()}"
            ),
        },
    )
