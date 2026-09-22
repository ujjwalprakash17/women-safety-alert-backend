import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    supabase_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )
    # Nullable: which of these is populated depends on the Supabase auth
    # provider used to sign in (phone-OTP vs. Google OAuth). At least one
    # is always present — enforced in code (get_current_user), not the DB.
    phone_number: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    # Null until onboarding is completed — the frontend gates every
    # authenticated page on both of these being set (see useAuthedUser).
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    consent_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Anti-misuse: set automatically after repeated false-alarm outcomes
    # (see resolve_sos in routers/sos.py). No admin tooling exists to
    # unban — that's done by flipping this directly in Supabase's Table
    # Editor after reviewing an appeal sent to the support email.
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ban_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
