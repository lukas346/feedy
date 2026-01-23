"""Add language column to app_settings table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-01-23 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add language column to app_settings table."""
    op.add_column(
        "app_settings",
        sa.Column("language", sa.String(5), nullable=True, default=None),
    )


def downgrade() -> None:
    """Remove language column from app_settings table."""
    op.drop_column("app_settings", "language")
