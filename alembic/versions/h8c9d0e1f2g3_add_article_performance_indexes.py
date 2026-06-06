"""Add performance indexes for articles table

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-01-25 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h8c9d0e1f2g3"
down_revision: Union[str, Sequence[str], None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes for is_read queries."""
    # Index on is_read - heavily filtered column
    op.create_index(
        op.f("ix_articles_is_read"),
        "articles",
        ["is_read"],
        unique=False,
    )

    # Composite index for common query pattern:
    # WHERE website_id IN (...) AND is_read = False ORDER BY published_at DESC
    op.create_index(
        "ix_articles_website_is_read_published",
        "articles",
        ["website_id", "is_read", "published_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove performance indexes."""
    op.drop_index("ix_articles_website_is_read_published", table_name="articles")
    op.drop_index(op.f("ix_articles_is_read"), table_name="articles")
