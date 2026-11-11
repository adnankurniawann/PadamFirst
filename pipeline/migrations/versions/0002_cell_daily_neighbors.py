"""Jumlah sel tetangga terbakar di cell_daily, fitur api dari PRD bagian 5.

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
    op.add_column("cell_daily", sa.Column("neighbors_burning", sa.Integer))


def downgrade() -> None:
    op.drop_column("cell_daily", "neighbors_burning")
