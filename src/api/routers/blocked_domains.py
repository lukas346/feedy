"""Blocked domains API router."""

from typing import Annotated, Sequence

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import (
    BlockDomainByArticleRequest,
    BlockDomainRequest,
    BlockedDomainResponse,
)
from application.services.domain_utils import extract_domain
from domain.models import BlockedDomain
from infrastructure.database import get_session
from infrastructure.repositories import ArticleRepository, BlockedDomainRepository

router = APIRouter(prefix="/api/blocked-domains", tags=["blocked-domains"])


@router.get("", response_model=list[BlockedDomainResponse])
def list_blocked_domains(
    session: Annotated[Session, Depends(get_session)],
) -> Sequence[BlockedDomain]:
    """List all blocked domains.

    Returns:
        List of blocked domains ordered by creation date (newest first)
    """
    repo = BlockedDomainRepository(session)
    result: Sequence[BlockedDomain] = repo.get_all()
    return result


@router.post("", response_model=BlockedDomainResponse, status_code=201)
def block_domain_by_article(
    request: BlockDomainByArticleRequest,
    session: Annotated[Session, Depends(get_session)],
) -> BlockedDomain:
    """Block a domain by article ID.

    Extracts the domain from the article's URL and adds it to the block list.

    Args:
        request: Request containing the article_id

    Returns:
        The newly created blocked domain

    Raises:
        HTTPException: 404 if article not found
        HTTPException: 400 if domain cannot be extracted
        HTTPException: 409 if domain is already blocked
    """
    article_repo = ArticleRepository(session)
    article = article_repo.get_by_id(request.article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    domain = extract_domain(article.url)
    if domain is None:
        raise HTTPException(
            status_code=400, detail="Could not extract domain from article URL"
        )

    blocked_repo = BlockedDomainRepository(session)
    existing = blocked_repo.get_by_domain(domain)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Domain is already blocked")

    return blocked_repo.create(domain)


@router.post("/direct", response_model=BlockedDomainResponse, status_code=201)
def block_domain_direct(
    request: BlockDomainRequest,
    session: Annotated[Session, Depends(get_session)],
) -> BlockedDomain:
    """Block a domain directly by domain name.

    Args:
        request: Request containing the domain to block

    Returns:
        The newly created blocked domain

    Raises:
        HTTPException: 400 if domain is empty
        HTTPException: 409 if domain is already blocked
    """
    domain = request.domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]

    if not domain:
        raise HTTPException(status_code=400, detail="Domain cannot be empty")

    repo = BlockedDomainRepository(session)
    existing = repo.get_by_domain(domain)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Domain is already blocked")

    return repo.create(domain)


@router.delete("/{blocked_domain_id}", status_code=204)
def unblock_domain(
    blocked_domain_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Unblock a domain by ID.

    Args:
        blocked_domain_id: The UUID of the blocked domain entry

    Raises:
        HTTPException: 404 if blocked domain not found
    """
    repo = BlockedDomainRepository(session)
    blocked_domain = repo.get_by_id(blocked_domain_id)
    if blocked_domain is None:
        raise HTTPException(status_code=404, detail="Blocked domain not found")

    repo.delete(blocked_domain)
