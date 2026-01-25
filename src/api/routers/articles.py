"""Article API router."""

from typing import Annotated, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas import (
    ArticleListResponse,
    ArticleResponse,
    MarkFavoriteRequest,
    MarkReadRequest,
)

# Note: mark_article_read and mark_article_favorite use ArticleListResponse
# (without content_html) to avoid sending large HTML content that may cause
# browser/HTMX to make spurious image requests from the JSON response.
from domain.models import Article
from infrastructure.database import get_session
from infrastructure.repositories import ArticleRepository

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=list[ArticleListResponse])
def list_articles(
    session: Annotated[Session, Depends(get_session)],
    website_id: Annotated[str | None, Query()] = None,
    is_read: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Article]:
    """List articles with pagination and filters.

    Args:
        website_id: Filter by website ID
        is_read: Filter by read status
        limit: Maximum number of articles to return (1-100)
        offset: Number of articles to skip
    """
    repo = ArticleRepository(session)
    result: Sequence[Article] = repo.get_list(
        website_id=website_id,
        is_read=is_read,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(
    article_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> Article:
    """Get a single article by ID.

    Args:
        article_id: The UUID of the article

    Returns:
        The article with full content

    Raises:
        HTTPException: 404 if article not found
    """
    repo = ArticleRepository(session)
    article = repo.get_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.patch("/{article_id}/read", response_model=ArticleListResponse)
def mark_article_read(
    article_id: str,
    request: MarkReadRequest,
    session: Annotated[Session, Depends(get_session)],
) -> Article:
    """Mark an article as read or unread.

    Args:
        article_id: The UUID of the article
        request: Request body containing is_read boolean

    Returns:
        The updated article (without content_html)

    Raises:
        HTTPException: 404 if article not found
    """
    repo = ArticleRepository(session)
    article = repo.get_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return repo.mark_as_read(article, request.is_read)


@router.patch("/{article_id}/favorite", response_model=ArticleListResponse)
def mark_article_favorite(
    article_id: str,
    request: MarkFavoriteRequest,
    session: Annotated[Session, Depends(get_session)],
) -> Article:
    """Mark an article as favorite or remove from favorites.

    Args:
        article_id: The UUID of the article
        request: Request body containing is_favorite boolean

    Returns:
        The updated article (without content_html)

    Raises:
        HTTPException: 404 if article not found
    """
    repo = ArticleRepository(session)
    article = repo.get_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return repo.mark_as_favorite(article, request.is_favorite)
