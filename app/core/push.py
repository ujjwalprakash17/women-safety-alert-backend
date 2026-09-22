import asyncio
import logging
import uuid

from pywebpush import WebPushException, webpush
from sqlalchemy import delete

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


async def send_push(subscription: PushSubscription, payload: str) -> None:
    """`webpush()` itself is blocking (uses `requests`, not `httpx`), so the
    call runs in a worker thread via `asyncio.to_thread` — but `send_push`
    stays an async function on the app's own event loop throughout. Passed
    directly to FastAPI's BackgroundTasks, which awaits async callables
    in-place, so one slow/dead subscription's thread-offload can't stall
    the others any more than the old thread-pool approach did.

    This matters beyond style: the shared async engine's connection pool is
    bound to the loop it was first used on. A previous version called
    `asyncio.run(_delete_dead_subscription(...))` from inside a plain sync
    function offloaded to a thread pool — that spins up a *second* event
    loop, and reusing a pooled asyncpg connection across two different loops
    raises "attached to a different loop". Staying on one loop end-to-end
    avoids that.
    """
    try:
        await asyncio.to_thread(
            webpush,
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
            await _delete_dead_subscription(subscription.id)
        else:
            logger.warning("webpush failed for subscription %s: %s", subscription.id, exc)


async def _delete_dead_subscription(subscription_id: uuid.UUID) -> None:
    async with async_session_maker() as db:
        await db.execute(delete(PushSubscription).where(PushSubscription.id == subscription_id))
        await db.commit()
