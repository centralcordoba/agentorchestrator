"""Esquema de la base de datos."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData()

ID = sa.String(64)
AGENT = sa.String(32)

requirements = sa.Table(
    "requirements",
    metadata,
    sa.Column("id", ID, primary_key=True),
    sa.Column("owner", sa.String(128), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("phi", sa.String(16), nullable=False),
    sa.Column("phi_set_by", sa.String(128), nullable=False, server_default=""),
    sa.Column("title_enc", sa.LargeBinary, nullable=False),
    sa.Column("description_enc", sa.LargeBinary, nullable=False),
    sa.Column("acceptance_criteria_enc", sa.LargeBinary, nullable=False),
    sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
    sa.Index("ix_requirements_created_at", sa.text("created_at DESC")),
)

attachments = sa.Table(
    "attachments",
    metadata,
    sa.Column("id", ID, primary_key=True),
    sa.Column(
        "requirement_id",
        ID,
        sa.ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("kind", sa.String(32), nullable=False),
    sa.Column("added_by", sa.String(128), nullable=False),
    sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("name_enc", sa.LargeBinary, nullable=False),
    sa.Column("detail_enc", sa.LargeBinary, nullable=False),
    sa.Column("repo_enc", sa.LargeBinary, nullable=True),
    sa.Index("ix_attachments_requirement", "requirement_id"),
)

plans = sa.Table(
    "plans",
    metadata,
    sa.Column(
        "requirement_id",
        ID,
        sa.ForeignKey("requirements.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("suggested_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("overridden_by", sa.String(128), nullable=False, server_default=""),
    sa.Column("items_enc", sa.LargeBinary, nullable=False),
)

runs = sa.Table(
    "runs",
    metadata,
    sa.Column("id", ID, primary_key=True),
    sa.Column(
        "requirement_id",
        ID,
        sa.ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("started_by", sa.String(128), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("error", sa.Text, nullable=False, server_default=""),
    sa.Column("enabled_agents", JSONB, nullable=False),
    sa.Column("profiles", JSONB, nullable=False),
    sa.Index("ix_runs_requirement_started", "requirement_id", sa.text("started_at DESC")),
    sa.Index("ix_runs_started_by", "started_by", sa.text("started_at DESC")),
    sa.Index("ix_runs_status", "status"),
)

run_executions = sa.Table(
    "run_executions",
    metadata,
    sa.Column("run_id", ID, sa.ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("agent_id", AGENT, primary_key=True),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("reason", sa.Text, nullable=False, server_default=""),
    sa.Column("error", sa.Text, nullable=False, server_default=""),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
    sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
    sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
    sa.Column("output_enc", sa.LargeBinary, nullable=True),
)

llm_calls = sa.Table(
    "llm_calls",
    metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("run_id", ID, sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
    sa.Column("agent_id", AGENT, nullable=False),
    sa.Column("provider", sa.String(32), nullable=False),
    sa.Column("model", sa.String(128), nullable=False),
    sa.Column("prompt_version", sa.Integer, nullable=False),
    sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
    sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
    sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
    sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
    sa.Column("attempts", sa.Integer, nullable=False, server_default="1"),
    sa.Column("tools_used", JSONB, nullable=False),
    sa.Column("tools_rejected", JSONB, nullable=False),
    sa.Column("at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("error", sa.Text, nullable=False, server_default=""),
    # Sin columnas de contenido a propósito: el registro es de metadatos.
    sa.Index("ix_llm_calls_run", "run_id"),
    sa.Index("ix_llm_calls_at", sa.text("at DESC")),
)

trace_events = sa.Table(
    "trace_events",
    metadata,
    sa.Column("run_id", ID, sa.ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("seq", sa.Integer, primary_key=True),
    sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("type", sa.String(32), nullable=False),
    sa.Column("agent", AGENT, nullable=True),
    sa.Column("to_agent", AGENT, nullable=True),
    sa.Column("tokens_in", sa.Integer, nullable=True),
    sa.Column("tokens_out", sa.Integer, nullable=True),
    sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
    sa.Column("payload_enc", sa.LargeBinary, nullable=False),
)

agent_profiles = sa.Table(
    "agent_profiles",
    metadata,
    sa.Column("scope", ID, primary_key=True),
    sa.Column("agent_id", AGENT, primary_key=True),
    sa.Column("provider", sa.String(32), nullable=False),
    sa.Column("model", sa.String(128), nullable=False),
    sa.Column("temperature", sa.Float, nullable=False),
    sa.Column("max_steps", sa.Integer, nullable=False),
    sa.Column("prompt_version", sa.Integer, nullable=False),
    sa.Column("system_prompt", sa.Text, nullable=False),
    sa.Column("task_prompt", sa.Text, nullable=False),
    sa.Column("versions", JSONB, nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

audit_entries = sa.Table(
    "audit_entries",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("actor", sa.String(128), nullable=False),
    sa.Column("action", sa.String(64), nullable=False),
    sa.Column("target", sa.String(128), nullable=False),
    sa.Column("detail", sa.Text, nullable=False, server_default=""),
    sa.Column("prev_hash", sa.String(64), nullable=False),
    sa.Column("hash", sa.String(64), nullable=False, unique=True),
    # Solo anexado: no hay borrado en cascada desde el requerimiento a propósito.
    sa.Index("ix_audit_at", sa.text("at DESC")),
    sa.Index("ix_audit_target", "target"),
)

id_counters = sa.Table(
    "id_counters",
    metadata,
    sa.Column("prefix", sa.String(16), primary_key=True),
    sa.Column("value", sa.BigInteger, nullable=False, server_default="0"),
)

GLOBAL_SCOPE = "*"

secrets = sa.Table(
    "secrets",
    metadata,
    sa.Column("id", ID, primary_key=True),
    sa.Column("kind", sa.String(32), nullable=False),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("scope", sa.String(64), nullable=False, server_default=""),
    #: **El valor va cifrado y nunca se lee desde SQL.** Es `LargeBinary` a propósito: no se
    #: puede filtrar, ordenar ni agrupar por él, y un volcado de la base no lo enseña.
    sa.Column("value_enc", sa.LargeBinary, nullable=False),
    sa.Column("username_enc", sa.LargeBinary, nullable=True),
    sa.Column("hint", sa.String(16), nullable=False, server_default=""),
    sa.Column("created_by", sa.String(128), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_by", sa.String(128), nullable=False, server_default=""),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("uses", sa.Integer, nullable=False, server_default="0"),
    #: Un secreto por (tipo, nombre, ámbito): guardar otra vez es rotar, no duplicar.
    sa.UniqueConstraint("kind", "name", "scope", name="uq_secrets_kind_name_scope"),
    sa.Index("ix_secrets_scope", "scope"),
)

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", ID, primary_key=True),
    sa.Column("email", sa.String(255), nullable=False, unique=True),
    sa.Column("name", sa.String(128), nullable=False),
    sa.Column("role", sa.String(32), nullable=False),
    sa.Column("provider", sa.String(16), nullable=False, server_default="local"),
    #: `scrypt$n$r$p$sal$hash`. Nulo cuando la identidad viene de OIDC: entonces no hay
    #: contraseña local que guardar.
    sa.Column("password_hash", sa.String(255), nullable=True),
    sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("failed_attempts", sa.Integer, nullable=False, server_default="0"),
    sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
)

sessions = sa.Table(
    "sessions",
    metadata,
    #: SHA-256 del testigo. **El testigo en sí no se guarda**: un volcado de esta tabla no
    #: permite suplantar a nadie.
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column(
        "user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("user_agent", sa.String(255), nullable=False, server_default=""),
    sa.Column("ip", sa.String(64), nullable=False, server_default=""),
    sa.Index("ix_sessions_user", "user_id"),
    sa.Index("ix_sessions_last_seen", "last_seen_at"),
)
