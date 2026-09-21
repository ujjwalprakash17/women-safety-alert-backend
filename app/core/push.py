import asyncio
import logging
import uuid

from pywebpush import WebPushException, webpush
from sqlalchemy import delete

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


def send_push(subscription: PushSubscription, payload: str) -> None:
    """Blocking (uses `requests`, not `httpx`) — must run off the event loop.

    Called via FastAPI's BackgroundTasks, one task per subscriber, so
    Starlette offloads each call to the thread pool independently and one
    slow/dead subscription can't stall the others.
    """
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_CONTACT_EMAIL},
        )
    except WebPushException as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code in (404, 410):
            # Dead subscription (browser unsubscribed / endpoint expired) —
            # clean it up so future triggers don't keep paying for it.
            asyncio.run(_delete_dead_subscription(subscription.id))
        else:
            logger.warning("webpush failed for subscription %s: %s", subscription.id, exc)


async def _delete_dead_subscription(subscription_id: uuid.UUID) -> None:
    # Fresh session: this runs in a background-thread worker, not on the
    # request's event loop, so the request's AsyncSession can't be reused.
    async with async_session_maker() as db:
        await db.execute(delete(PushSubscription).where(PushSubscription.id == subscription_id))
        await db.commit()
