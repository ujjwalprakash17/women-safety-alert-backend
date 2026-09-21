"""enable postgis and create users

Revision ID: ea1b14d5338d
Revises:
Create Date: 2026-09-21 22:07:08.994199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ea1b14d5338d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Concrete proof PostGIS is wired end-to-end this milestone, even with no
    # geometry columns yet (those arrive in Milestone 2's nearby-responder query).
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "supabase_user_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("phone_number", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("supabase_user_id", name="uq_users_supabase_user_id"),
        sa.UniqueConstraint("phone_number", name="uq_users_phone_number"),
    )
    op.create_index(
        "ix_users_supabase_user_id", "users", ["supabase_user_id"], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_users_supabase_user_id", table_name="users")
    op.drop_table("users")
    # Deliberately not dropping the postgis extension on downgrade — other
    # tables may depend on it by the time this would ever run.
