import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SosOutcome = Literal["real", "false_alarm", "test"]


class SosTriggerRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class SosLocationUpdateRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class SosResolveRequest(BaseModel):
    outcome: SosOutcome


class SosSessionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: Literal["active", "resolved"]
    outcome: SosOutcome | None
    lat: float
    lng: float
    display_name: str | None
    phone_number: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class NearbySosSession(SosSessionRead):
    distance_meters: float
