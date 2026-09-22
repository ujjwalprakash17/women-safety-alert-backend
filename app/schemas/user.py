import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supabase_user_id: uuid.UUID
    phone_number: str | None
    email: str | None
    display_name: str | None
    avatar_url: str | None
    consent_accepted_at: datetime | None
    default_radius_km: int
    is_banned: bool
    ban_reason: str | None
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    phone_number: str | None = None
    avatar_url: str | None = None
    default_radius_km: int | None = Field(default=None, ge=1, le=50)
    # Required (and must be true) only the first time — see update_me in
    # routers/me.py. Optional afterwards so editing your name later doesn't
    # force re-ticking the consent box.
    accept_consent: bool | None = None
