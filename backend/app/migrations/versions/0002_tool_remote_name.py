"""tools: remote name

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tools", sa.Column("remote_name", sa.String(100)))


def downgrade() -> None:
    op.drop_column("tools", "remote_name")
