"""add profile fields to users

Revision ID: af88cd5fc647
Revises: c4ca00206004
Create Date: 2026-09-22 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af88cd5fc647'
down_revision: Union[str, Sequence[str], None] = 'c4ca00206004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("display_name", sa.String(), nullable=True))
    op.add_column(
        "users", sa.Column("consent_accepted_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "consent_accepted_at")
    op.drop_column("users", "display_name")
