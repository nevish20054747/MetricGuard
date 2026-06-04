"""initial_schema

Revision ID: b7a7bd7126eb
Revises:
Create Date: 2026-06-04 19:03:00.000000

This migration brings an EXISTING TiDB database (with metrics and anomalies
tables already created via Base.metadata.create_all) in sync with the
current ORM models by adding missing audit columns, indexes, and constraints.

For a brand-new database the tables will already have been created by the
application startup (create_all), so these ALTER statements use
'IF NOT EXISTS' style safety where possible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'b7a7bd7126eb'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── helpers ──────────────────────────────────────────────────────────

def _column_exists(conn, table: str, column: str) -> bool:
    """Check whether a column already exists in a table (MySQL / TiDB)."""
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "AND table_name = :tbl AND column_name = :col"
        ),
        {"tbl": table, "col": column},
    )
    return result.scalar() > 0


def _index_exists(conn, table: str, index_name: str) -> bool:
    """Check whether an index already exists (MySQL / TiDB)."""
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() "
            "AND table_name = :tbl AND index_name = :idx"
        ),
        {"tbl": table, "idx": index_name},
    )
    return result.scalar() > 0


# ── upgrade ──────────────────────────────────────────────────────────

def upgrade() -> None:
    conn = op.get_bind()

    # --- metrics table: add audit columns if missing ---
    if not _column_exists(conn, "metrics", "created_at"):
        op.add_column(
            "metrics",
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    if not _column_exists(conn, "metrics", "updated_at"):
        op.add_column(
            "metrics",
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    # --- metrics table: ensure indexes exist ---
    if not _index_exists(conn, "metrics", "ix_metrics_timestamp"):
        op.create_index(op.f("ix_metrics_timestamp"), "metrics", ["timestamp"], unique=False)

    # --- anomalies table: add audit columns if missing ---
    if not _column_exists(conn, "anomalies", "created_at"):
        op.add_column(
            "anomalies",
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    if not _column_exists(conn, "anomalies", "updated_at"):
        op.add_column(
            "anomalies",
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    # --- anomalies table: add detected_by column if missing ---
    if not _column_exists(conn, "anomalies", "detected_by"):
        op.add_column(
            "anomalies",
            sa.Column("detected_by", sa.String(100), nullable=False, server_default="unknown"),
        )

    # --- anomalies table: ensure indexes exist ---
    if not _index_exists(conn, "anomalies", "ix_anomalies_timestamp"):
        op.create_index(op.f("ix_anomalies_timestamp"), "anomalies", ["timestamp"], unique=False)

    if not _index_exists(conn, "anomalies", "ix_anomalies_severity"):
        op.create_index(op.f("ix_anomalies_severity"), "anomalies", ["severity"], unique=False)

    if not _index_exists(conn, "anomalies", "ix_anomalies_metric_id"):
        op.create_index(op.f("ix_anomalies_metric_id"), "anomalies", ["metric_id"], unique=False)


# ── downgrade ────────────────────────────────────────────────────────

def downgrade() -> None:
    conn = op.get_bind()

    # Remove audit columns and extra indexes that this migration added.
    # We intentionally do NOT drop the tables themselves because they
    # pre-existed this migration.

    if _index_exists(conn, "anomalies", "ix_anomalies_metric_id"):
        op.drop_index(op.f("ix_anomalies_metric_id"), table_name="anomalies")

    if _index_exists(conn, "anomalies", "ix_anomalies_severity"):
        op.drop_index(op.f("ix_anomalies_severity"), table_name="anomalies")

    if _index_exists(conn, "anomalies", "ix_anomalies_timestamp"):
        op.drop_index(op.f("ix_anomalies_timestamp"), table_name="anomalies")

    if _column_exists(conn, "anomalies", "updated_at"):
        op.drop_column("anomalies", "updated_at")

    if _column_exists(conn, "anomalies", "created_at"):
        op.drop_column("anomalies", "created_at")

    if _index_exists(conn, "metrics", "ix_metrics_timestamp"):
        op.drop_index(op.f("ix_metrics_timestamp"), table_name="metrics")

    if _column_exists(conn, "metrics", "updated_at"):
        op.drop_column("metrics", "updated_at")

    if _column_exists(conn, "metrics", "created_at"):
        op.drop_column("metrics", "created_at")
