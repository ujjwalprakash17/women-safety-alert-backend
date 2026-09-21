"""support google oauth users

Revision ID: 66b48b72fbac
Revises: ea1b14d5338d
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66b48b72fbac'
down_revision: Union[str, Sequence[str], None] = 'ea1b14d5338d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # phone_number is no longer mandatory: Google-OAuth users authenticate
    # with an email instead. At least one of the two is still required, but
    # that's enforced in app code (get_current_user), not a DB constraint.
    op.alter_column("users", "phone_number", existing_type=sa.String(), nullable=True)
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "email")
    op.alter_column("users", "phone_number", existing_type=sa.String(), nullable=False)
