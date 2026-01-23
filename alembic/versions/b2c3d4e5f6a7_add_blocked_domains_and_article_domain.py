"""Add blocked_domains table and article domain column

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-20 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from application.services.domain_utils import extract_domain

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add blocked_domains table and article.domain column."""
    # Create blocked_domains table
    op.create_table(
        "blocked_domains",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domain", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # Add domain column to articles table
    op.add_column(
        "articles",
        sa.Column("domain", sa.String(255), nullable=True, index=True),
    )

    # Backfill domain for existing articles
    conn = op.get_bind()
    articles = conn.execute(sa.text("SELECT id, url FROM articles")).fetchall()
    for article_id, url in articles:
        domain = extract_domain(url)
        if domain:
            conn.execute(
                sa.text("UPDATE articles SET domain = :domain WHERE id = :id"),
                {"domain": domain, "id": article_id},
            )


def downgrade() -> None:
    """Remove blocked_domains table and article.domain column."""
    op.drop_column("articles", "domain")
    op.drop_table("blocked_domains")
