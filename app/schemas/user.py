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
    consent_accepted_at: datetime | None
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    phone_number: str | None = None
    accept_consent: bool
