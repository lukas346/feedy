"""Add app_settings and sessions tables for authentication

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-01-20 16:00:00.000000

"""

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add app_settings and sessions tables."""
    # Create app_settings table (single row for single-user auth)
    op.create_table(
        "app_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("password_salt", sa.String(64), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Create sessions table
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )

    # Create default settings with password "admin"
    conn = op.get_bind()
    settings_id = str(uuid.uuid4())
    salt = secrets.token_hex(32)
    password_hash = hashlib.sha256(("admin" + salt).encode()).hexdigest()
    now = datetime.utcnow()

    conn.execute(
        sa.text(
            """
            INSERT INTO app_settings (id, password_hash, password_salt,
                                      must_change_password, created_at, updated_at)
            VALUES (:id, :password_hash, :password_salt,
                    :must_change_password, :created_at, :updated_at)
            """
        ),
        {
            "id": settings_id,
            "password_hash": password_hash,
            "password_salt": salt,
            "must_change_password": True,
            "created_at": now,
            "updated_at": now,
        },
    )


def downgrade() -> None:
    """Remove app_settings and sessions tables."""
    op.drop_table("sessions")
    op.drop_table("app_settings")
