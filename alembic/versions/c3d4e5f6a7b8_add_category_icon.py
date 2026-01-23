"""Add icon column to categories table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-20 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add icon column to categories table."""
    op.add_column(
        "categories",
        sa.Column("icon", sa.String(32), nullable=True, default="tag"),
    )

    # Set default value for existing categories
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE categories SET icon = 'tag' WHERE icon IS NULL"))


def downgrade() -> None:
    """Remove icon column from categories table."""
    op.drop_column("categories", "icon")
