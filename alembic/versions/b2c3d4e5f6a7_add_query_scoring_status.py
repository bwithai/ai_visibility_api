"""add scoring_status and error_message to discovered_queries

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-20 07:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("discovered_queries", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "scoring_status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(
            sa.Column("error_message", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("discovered_queries", schema=None) as batch_op:
        batch_op.drop_column("error_message")
        batch_op.drop_column("scoring_status")
