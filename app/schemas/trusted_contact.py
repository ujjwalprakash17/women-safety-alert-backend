import uuid
from datetime import datetime

from pydantic import BaseModel


class TrustedContactCreate(BaseModel):
    name: str
    phone_number: str
    relationship_label: str | None = None


class TrustedContactRead(BaseModel):
    id: uuid.UUID
    name: str
    phone_number: str
    relationship_label: str | None
    created_at: datetime
