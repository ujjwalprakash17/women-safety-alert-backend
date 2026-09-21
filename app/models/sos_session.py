import uuid
from datetime import datetime

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Single source of truth for the column's PostGIS type — reused by the
# router when it casts a client-supplied (lat, lng) into the same type
# for ST_DWithin/ST_Distance comparisons.
SOS_LOCATION_TYPE = Geography(geometry_type="POINT", srid=4326, spatial_index=False)


class SosSession(Base):
    __tablename__ = "sos_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'resolved')", name="ck_sos_sessions_status"),
        CheckConstraint(
            "outcome IN ('real', 'false_alarm', 'test') OR outcome IS NULL",
            name="ck_sos_sessions_outcome",
        ),
        CheckConstraint(
            "(status = 'resolved') = (outcome IS NOT NULL)",
            name="ck_sos_sessions_resolved_has_outcome",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    # spatial_index=False: the GIST index is hand-created in the migration,
    # not left to GeoAlchemy2's own DDL-event/autogenerate machinery.
    location: Mapped[WKBElement] = mapped_column(SOS_LOCATION_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
