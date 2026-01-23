"""Category API router."""

import re
import unicodedata
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.schemas import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)
from domain.models import Category
from infrastructure.database import get_session
from infrastructure.repositories import CategoryRepository

router = APIRouter(prefix="/api/categories", tags=["categories"])


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from a name."""
    # Normalize unicode characters
    normalized = unicodedata.normalize("NFKD", name)
    # Remove non-ASCII characters
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r"[^\w\s-]", "", ascii_text).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug


@router.get("", response_model=list[CategoryListResponse])
def list_categories(
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, Any]]:
    """List all categories with website counts, ordered by name."""
    repo = CategoryRepository(session)
    categories = repo.get_all_with_website_counts()

    return [
        {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "icon": cat.icon,
            "created_at": cat.created_at,
            "website_count": website_count,
        }
        for cat, website_count in categories
    ]


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    data: CategoryCreate,
    session: Annotated[Session, Depends(get_session)],
) -> Category:
    """Create a new category."""
    repo = CategoryRepository(session)
    return repo.create(
        name=data.name,
        slug=generate_slug(data.name),
        icon=data.icon,
    )


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: str,
    data: CategoryUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> Category:
    """Update a category by ID."""
    repo = CategoryRepository(session)
    category = repo.get_by_id(category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    new_slug = generate_slug(data.name) if data.name is not None else None
    return repo.update(category, name=data.name, slug=new_slug, icon=data.icon)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Delete a category by ID."""
    repo = CategoryRepository(session)
    category = repo.get_by_id(category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    repo.delete(category)
