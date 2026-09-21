from pydantic import BaseModel


class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushSubscribeResponse(BaseModel):
    id: str
    endpoint: str


class VapidPublicKey(BaseModel):
    public_key: str
