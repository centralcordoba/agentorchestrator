"""usuarios y sesiones

`users.password_hash` guarda `scrypt$n$r$p$sal$hash`, nunca la contraseña. `sessions.id` es el
SHA-256 del testigo que viaja en la cookie: el testigo en sí no está en la base, así que un
volcado no permite suplantar a nadie.

Revision ID: d83b5e1a7c94
Revises: c41f7a29b5d2
Create Date: 2026-09-16 14:55:00.000000+00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d83b5e1a7c94"
down_revision = "c41f7a29b5d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=16), server_default="local", nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=255), server_default="", nullable=False),
        sa.Column("ip", sa.String(length=64), server_default="", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_user", "sessions", ["user_id"], unique=False)
    op.create_index("ix_sessions_last_seen", "sessions", ["last_seen_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sessions_last_seen", table_name="sessions")
    op.drop_index("ix_sessions_user", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
