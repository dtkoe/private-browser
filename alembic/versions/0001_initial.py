"""initial schema with app_settings

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("theme", sa.String(), nullable=False, server_default="dark"),
        sa.Column("language", sa.String(), nullable=False, server_default="ru"),
        sa.Column("camoufox_version", sa.String(), nullable=True),
        sa.Column("auto_update_check", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("api_port", sa.Integer(), nullable=False, server_default="8769"),
        sa.Column("kdf_salt", sa.LargeBinary(length=16), nullable=False),
        sa.Column("kdf_verifier", sa.LargeBinary(length=32), nullable=False),
        sa.Column("kdf_params_json", sa.String(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_app_settings_singleton"),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
