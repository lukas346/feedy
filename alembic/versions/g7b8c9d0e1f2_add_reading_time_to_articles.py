"""Add reading_time_minutes column to articles table

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-01-23 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def calculate_reading_time_for_migration(html_content: str | None) -> int | None:
    """Calculate reading time inline for migration (avoids import issues)."""
    import math

    from bs4 import BeautifulSoup

    if not html_content or not html_content.strip():
        return None

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        if not text:
            return None

        word_count = len(text.split())
        if word_count == 0:
            return None

        minutes = math.ceil(word_count / 200)
        return max(1, minutes)
    except Exception:
        return None


def upgrade() -> None:
    """Add reading_time_minutes column and backfill existing articles."""
    # Add the column
    op.add_column(
        "articles",
        sa.Column("reading_time_minutes", sa.Integer(), nullable=True),
    )

    # Backfill existing articles
    connection = op.get_bind()
    articles = connection.execute(
        sa.text("SELECT id, content_html FROM articles WHERE content_html IS NOT NULL")
    ).fetchall()

    for article_id, content_html in articles:
        reading_time = calculate_reading_time_for_migration(content_html)
        if reading_time is not None:
            connection.execute(
                sa.text(
                    "UPDATE articles SET reading_time_minutes = :reading_time "
                    "WHERE id = :id"
                ),
                {"reading_time": reading_time, "id": article_id},
            )


def downgrade() -> None:
    """Remove reading_time_minutes column from articles table."""
    op.drop_column("articles", "reading_time_minutes")
