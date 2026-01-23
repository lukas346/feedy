"""Rename content_markdown to content_html

Revision ID: a1b2c3d4e5f6
Revises: c07c4f0e1ab6
Create Date: 2026-01-20 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c07c4f0e1ab6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename content_markdown column to content_html."""
    op.alter_column(
        "articles",
        "content_markdown",
        new_column_name="content_html",
    )


def downgrade() -> None:
    """Revert content_html column back to content_markdown."""
    op.alter_column(
        "articles",
        "content_html",
        new_column_name="content_markdown",
    )
