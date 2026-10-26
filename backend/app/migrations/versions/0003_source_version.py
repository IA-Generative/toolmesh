"""sources: version

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("version", sa.String(100)))


def downgrade() -> None:
    op.drop_column("sources", "version")
