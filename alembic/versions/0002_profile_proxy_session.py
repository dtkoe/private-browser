"""profile + proxy + session

Revision ID: 0002_profile_proxy_session
Revises: 0001_initial
Create Date: 2026-05-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_profile_proxy_session"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxy",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("host", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("password", sa.String(), nullable=True),
        sa.Column("last_checked_at", sa.BigInteger(), nullable=True),
        sa.Column("last_check_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_ip", sa.String(), nullable=True),
        sa.Column("last_country", sa.String(8), nullable=True),
        sa.Column("last_city", sa.String(), nullable=True),
        sa.Column("last_timezone", sa.String(), nullable=True),
        sa.Column("last_latency_ms", sa.Integer(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("idx_proxy_last_check", "proxy", ["last_checked_at"])

    op.create_table(
        "profile",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("last_opened_at", sa.BigInteger(), nullable=True),
        sa.Column("open_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("proxy_id", sa.String(64), nullable=True),
        sa.Column("user_data_dir", sa.String(), nullable=False),
        sa.Column("total_sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_duration_sec", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_profile_status", "profile", ["status"])
    op.create_index("idx_profile_last_opened", "profile", ["last_opened_at"])

    op.create_table(
        "session",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("profile_id", sa.String(64), nullable=False),
        sa.Column("started_at", sa.BigInteger(), nullable=False),
        sa.Column("ended_at", sa.BigInteger(), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("proxy_id", sa.String(64), nullable=True),
        sa.Column("exit_ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proxy_id"], ["proxy.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_session_profile", "session", ["profile_id", "started_at"])


def downgrade() -> None:
    op.drop_index("idx_session_profile", table_name="session")
    op.drop_table("session")
    op.drop_index("idx_profile_last_opened", table_name="profile")
    op.drop_index("idx_profile_status", table_name="profile")
    op.drop_table("profile")
    op.drop_index("idx_proxy_last_check", table_name="proxy")
    op.drop_table("proxy")
