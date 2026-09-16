"""bóveda de secretos

El valor va en `value_enc` (LargeBinary, cifrado con Fernet fuera de la base). No hay ninguna
columna con el valor en claro, y eso es deliberado: un volcado de la base no enseña ningún token.

Revision ID: c41f7a29b5d2
Revises: 888df80a11a2
Create Date: 2026-09-16 14:25:00.000000+00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c41f7a29b5d2"
down_revision = "888df80a11a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "secrets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=64), server_default="", nullable=False),
        sa.Column("value_enc", sa.LargeBinary(), nullable=False),
        sa.Column("username_enc", sa.LargeBinary(), nullable=True),
        sa.Column("hint", sa.String(length=16), server_default="", nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=128), server_default="", nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uses", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "name", "scope", name="uq_secrets_kind_name_scope"),
    )
    op.create_index("ix_secrets_scope", "secrets", ["scope"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_secrets_scope", table_name="secrets")
    op.drop_table("secrets")
