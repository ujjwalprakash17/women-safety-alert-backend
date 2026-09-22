"""add ban fields to users

Revision ID: 4a1df564a222
Revises: af88cd5fc647
Create Date: 2026-09-22 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a1df564a222'
down_revision: Union[str, Sequence[str], None] = 'af88cd5fc647'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users", sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("ban_reason", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "ban_reason")
    op.drop_column("users", "banned_at")
    op.drop_column("users", "is_banned")
