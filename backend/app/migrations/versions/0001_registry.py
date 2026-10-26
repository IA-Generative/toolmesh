"""registry: sources and tools

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("url", sa.String(2048)),
        sa.Column("openapi_url", sa.String(2048)),
        sa.Column("auth_mode", sa.String(20), nullable=False),
        sa.Column("audience", sa.String(255)),
        sa.Column("endpoint_include", sa.JSON(), nullable=False),
        sa.Column("endpoint_exclude", sa.JSON(), nullable=False),
        sa.Column("required_role", sa.String(100)),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "tools",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("source_id", sa.String(32), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("method", sa.String(10)),
        sa.Column("path", sa.String(2048)),
        sa.Column("input_schema", sa.JSON()),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_tools_source_id", "tools", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_tools_source_id", table_name="tools")
    op.drop_table("tools")
    op.drop_table("sources")
