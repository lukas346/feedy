"""Website API router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.schemas import (
    WebsiteCreate,
    WebsiteListResponse,
    WebsiteResponse,
    WebsiteUpdate,
)
from application.services.validators import validate_url
from domain.models import Website
from infrastructure.database import get_session
from infrastructure.repositories import CategoryRepository, WebsiteRepository

router = APIRouter(prefix="/api/websites", tags=["websites"])


@router.get("", response_model=list[WebsiteListResponse])
def list_websites(
    session: Annotated[Session, Depends(get_session)],
    category_id: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    """List all websites with unread article counts, optionally filtered by category."""
    repo = WebsiteRepository(session)
    websites = repo.get_all_with_unread_counts(category_id)

    return [
        {
            "id": website.id,
            "name": website.name,
            "url": website.url,
            "rss_url": website.rss_url,
            "category_id": website.category_id,
            "fetch_interval_minutes": website.fetch_interval_minutes,
            "last_fetched_at": website.last_fetched_at,
            "created_at": website.created_at,
            "unread_count": unread_count,
        }
        for website, unread_count in websites
    ]


@router.post(
    "",
    response_model=WebsiteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_website(
    data: WebsiteCreate,
    session: Annotated[Session, Depends(get_session)],
) -> Website:
    """Create a new website."""
    # Validate URLs
    if not validate_url(data.url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid website URL",
        )
    if not validate_url(data.rss_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid RSS URL",
        )

    # Validate category exists
    category_repo = CategoryRepository(session)
    category = category_repo.get_by_id(data.category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # Check for duplicate RSS URL
    website_repo = WebsiteRepository(session)
    existing = website_repo.get_by_rss_url(data.rss_url)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A feed with this RSS URL already exists",
        )

    return website_repo.create(
        name=data.name,
        url=data.url,
        rss_url=data.rss_url,
        category_id=data.category_id,
        fetch_interval_minutes=data.fetch_interval_minutes,
    )


@router.put("/{website_id}", response_model=WebsiteResponse)
def update_website(
    website_id: str,
    data: WebsiteUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> Website:
    """Update a website by ID."""
    website_repo = WebsiteRepository(session)
    website = website_repo.get_by_id(website_id)
    if website is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    # Validate category exists if being updated
    if data.category_id is not None:
        category_repo = CategoryRepository(session)
        category = category_repo.get_by_id(data.category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

    # Validate URLs if being updated
    if data.url is not None and not validate_url(data.url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid website URL",
        )
    if data.rss_url is not None and not validate_url(data.rss_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid RSS URL",
        )

    # Check for duplicate RSS URL (excluding current website)
    if data.rss_url is not None:
        existing = website_repo.get_by_rss_url(data.rss_url)
        if existing is not None and existing.id != website_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A feed with this RSS URL already exists",
            )

    return website_repo.update(
        website,
        name=data.name,
        url=data.url,
        rss_url=data.rss_url,
        category_id=data.category_id,
        fetch_interval_minutes=data.fetch_interval_minutes,
    )


@router.delete("/{website_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_website(
    website_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Delete a website by ID. Cascades deletion to all associated articles."""
    repo = WebsiteRepository(session)
    website = repo.get_by_id(website_id)
    if website is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )
    repo.delete(website)
