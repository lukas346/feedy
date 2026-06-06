"""Repository for BlockedDomain data access."""

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.models import BlockedDomain


class BlockedDomainRepository:
    """Repository for BlockedDomain data access operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_all(self) -> Sequence[BlockedDomain]:
        """Get all blocked domains, ordered by creation date (newest first)."""
        stmt = select(BlockedDomain).order_by(BlockedDomain.created_at.desc())
        result: Sequence[BlockedDomain] = self.session.scalars(stmt).all()
        return result

    def get_by_id(self, blocked_domain_id: str) -> BlockedDomain | None:
        """Get a blocked domain by its ID."""
        stmt = select(BlockedDomain).where(BlockedDomain.id == blocked_domain_id)
        return self.session.scalars(stmt).first()

    def get_by_domain(self, domain: str) -> BlockedDomain | None:
        """Get a blocked domain by domain name."""
        stmt = select(BlockedDomain).where(BlockedDomain.domain == domain)
        return self.session.scalars(stmt).first()

    def is_blocked(self, domain: str) -> bool:
        """Check if a domain is blocked."""
        return self.get_by_domain(domain) is not None

    def create(self, domain: str) -> BlockedDomain:
        """Create a new blocked domain entry."""
        blocked_domain = BlockedDomain(domain=domain)
        self.session.add(blocked_domain)
        self.session.flush()
        self.session.refresh(blocked_domain)
        return blocked_domain

    def delete(self, blocked_domain: BlockedDomain) -> None:
        """Delete a blocked domain entry."""
        self.session.delete(blocked_domain)
        self.session.flush()
