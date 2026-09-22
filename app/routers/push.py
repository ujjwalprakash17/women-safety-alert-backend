from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.schemas.push_subscription import (
    PushSubscribeRequest,
    PushSubscribeResponse,
    VapidPublicKey,
)

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key", response_model=VapidPublicKey)
async def get_vapid_public_key() -> VapidPublicKey:
    return VapidPublicKey(public_key=settings.VAPID_PUBLIC_KEY)


@router.post("/subscribe", response_model=PushSubscribeResponse)
async def subscribe(
    body: PushSubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PushSubscribeResponse:
    # Upsert by endpoint: the same browser subscribing again (e.g. a
    # different account signs in on the same browser profile) re-owns the
    # row to whoever is currently authenticated, rather than erroring or
    # creating a duplicate.
    stmt = (
        pg_insert(PushSubscription)
        .values(
            user_id=current_user.id,
            endpoint=body.endpoint,
            p256dh=body.p256dh,
            auth=body.auth,
        )
        .on_conflict_do_update(
            index_elements=[PushSubscription.endpoint],
            set_={
                "user_id": current_user.id,
                "p256dh": body.p256dh,
                "auth": body.auth,
            },
        )
        .returning(PushSubscription.id, PushSubscription.endpoint)
    )
    row = (await db.execute(stmt)).one()
    await db.commit()
    return PushSubscribeResponse(id=str(row.id), endpoint=row.endpoint)


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    endpoint: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    # Scoped to the current user's own rows — silently succeeds even if the
    # endpoint doesn't match anything of theirs (already-unsubscribed is not
    # an error worth surfacing).
    await db.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == endpoint,
            PushSubscription.user_id == current_user.id,
        )
    )
    await db.commit()
