"""search events, clicks and feedback

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_sub", sa.String(255), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("took_ms", sa.Integer(), nullable=False),
    )
    op.create_index("ix_search_events_created_at", "search_events", ["created_at"])
    op.create_table(
        "search_clicks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("search_id", sa.String(32), sa.ForeignKey("search_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool", sa.String(100), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_search_clicks_search_id", "search_clicks", ["search_id"])
    op.create_table(
        "search_feedback",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("search_id", sa.String(32), sa.ForeignKey("search_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_sub", sa.String(255), nullable=False),
        sa.Column("verdict", sa.String(10), nullable=False),
        sa.Column("expected", sa.JSON(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_search_feedback_search_id", "search_feedback", ["search_id"])
    op.create_index("ix_search_feedback_status", "search_feedback", ["status"])


def downgrade() -> None:
    op.drop_table("search_feedback")
    op.drop_table("search_clicks")
    op.drop_table("search_events")
