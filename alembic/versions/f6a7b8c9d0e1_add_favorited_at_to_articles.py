"""Add favorited_at column to articles table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-01-23 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add favorited_at column to articles table."""
    op.add_column(
        "articles",
        sa.Column("favorited_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f("ix_articles_favorited_at"), "articles", ["favorited_at"], unique=False
    )


def downgrade() -> None:
    """Remove favorited_at column from articles table."""
    op.drop_index(op.f("ix_articles_favorited_at"), table_name="articles")
    op.drop_column("articles", "favorited_at")
