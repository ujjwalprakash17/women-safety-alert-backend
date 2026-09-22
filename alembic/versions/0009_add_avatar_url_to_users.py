"""add avatar_url to users

Revision ID: 872d4b11a629
Revises: ac83ecbbe25a
Create Date: 2026-09-22 05:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '872d4b11a629'
down_revision: Union[str, Sequence[str], None] = 'ac83ecbbe25a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("avatar_url", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "avatar_url")
