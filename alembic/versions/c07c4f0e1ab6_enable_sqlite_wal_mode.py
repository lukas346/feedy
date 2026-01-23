"""Enable SQLite WAL (Write-Ahead Logging) mode for better concurrency.

Revision ID: c07c4f0e1ab6
Revises: f9c59b64bcd0
Create Date: 2026-01-20 02:01:14.010533

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "c07c4f0e1ab6"
down_revision: Union[str, Sequence[str], None] = "f9c59b64bcd0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable WAL mode for SQLite."""
    connection = op.get_bind()
    connection.execute(text("PRAGMA journal_mode=WAL"))


def downgrade() -> None:
    """Revert to default DELETE journal mode."""
    connection = op.get_bind()
    connection.execute(text("PRAGMA journal_mode=DELETE"))
