"""add default radius to users

Revision ID: ac83ecbbe25a
Revises: 4a1df564a222
Create Date: 2026-09-22 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac83ecbbe25a'
down_revision: Union[str, Sequence[str], None] = '4a1df564a222'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("default_radius_km", sa.Integer(), nullable=False, server_default="5"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "default_radius_km")
