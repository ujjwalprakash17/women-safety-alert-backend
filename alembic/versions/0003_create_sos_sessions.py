"""create sos sessions table

Revision ID: d9766fcdba8a
Revises: 66b48b72fbac
Create Date: 2026-09-22 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from geoalchemy2 import Geography


# revision identifiers, used by Alembic.
revision: str = 'd9766fcdba8a'
down_revision: Union[str, Sequence[str], None] = '66b48b72fbac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sos_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("outcome", sa.String(), nullable=True),
        # Geography, not Geometry: ST_DWithin/ST_Distance need accurate
        # real-world meters over WGS84, without manually reprojecting to a
        # planar SRID per query. spatial_index=False — the GIST index is
        # created explicitly below, kept as the single source of the index.
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'resolved')", name="ck_sos_sessions_status"),
        sa.CheckConstraint(
            "outcome IN ('real', 'false_alarm', 'test') OR outcome IS NULL",
            name="ck_sos_sessions_outcome",
        ),
        sa.CheckConstraint(
            "(status = 'resolved') = (outcome IS NOT NULL)",
            name="ck_sos_sessions_resolved_has_outcome",
        ),
    )
    op.create_index("ix_sos_sessions_user_id", "sos_sessions", ["user_id"])
    # GIST index — required for ST_DWithin/ST_Distance in the nearby-sessions
    # query to use an index scan instead of a full table scan as data grows.
    op.create_index(
        "idx_sos_sessions_location",
        "sos_sessions",
        ["location"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_sos_sessions_location", table_name="sos_sessions")
    op.drop_index("ix_sos_sessions_user_id", table_name="sos_sessions")
    op.drop_table("sos_sessions")
