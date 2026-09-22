import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.push import send_push
from app.core.security import get_current_user
from app.core.ws_manager import sos_ws_manager
from app.db.session import get_db
from app.models.push_subscription import PushSubscription
from app.models.sos_session import SOS_LOCATION_TYPE, SosSession
from app.models.user import User
from app.schemas.sos_session import (
    NearbySosSession,
    SosLocationUpdateRequest,
    SosResolveRequest,
    SosSessionRead,
    SosTriggerRequest,
)

router = APIRouter(prefix="/sos", tags=["sos"])

_GEOMETRY_POINT = Geometry(geometry_type="POINT", srid=4326)

# Anti-misuse: after this many sessions resolved as "false_alarm" (not
# "test", which is an expected/allowed outcome), the account auto-suspends.
FALSE_ALARM_BAN_THRESHOLD = 3
SUPPORT_EMAIL = "ujjwalprakash144@gmail.com"


def _point(lat: float, lng: float):
    # Explicit cast to the *same* Geography type as the column. Geometry ->
    # geography is not an implicit cast in Postgres: without this, ST_DWithin/
    # ST_Distance either fail to resolve an overload, or silently match the
    # geometry-based overload and return degrees instead of meters.
    return cast(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326), SOS_LOCATION_TYPE)


async def _get_session_row(db: AsyncSession, session_id: uuid.UUID):
    stmt = (
        select(
            SosSession,
            func.ST_Y(cast(SosSession.location, _GEOMETRY_POINT)).label("lat"),
            func.ST_X(cast(SosSession.location, _GEOMETRY_POINT)).label("lng"),
            User.display_name,
            User.phone_number,
            User.avatar_url,
        )
        .join(User, User.id == SosSession.user_id)
        .where(SosSession.id == session_id)
        # expire_on_commit=False means an already identity-mapped instance
        # won't otherwise pick up attributes written by the just-committed flush.
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).one_or_none()


def _to_read(
    session: SosSession,
    lat: float,
    lng: float,
    display_name: str | None,
    phone_number: str | None,
    avatar_url: str | None,
) -> SosSessionRead:
    return SosSessionRead(
        id=session.id,
        user_id=session.user_id,
        status=session.status,
        outcome=session.outcome,
        lat=lat,
        lng=lng,
        # Shown to whoever is watching this session (any authenticated user
        # currently — no responder/KYC tier exists yet) so they know who
        # they're responding to and can reach them directly.
        display_name=display_name,
        phone_number=phone_number,
        avatar_url=avatar_url,
        created_at=session.created_at,
        updated_at=session.updated_at,
        resolved_at=session.resolved_at,
    )


async def _get_active_session_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> SosSession | None:
    # .first() rather than scalar_one_or_none(): accounts created before the
    # duplicate-session guard was added could already have more than one row
    # marked "active" in the database, which would otherwise raise
    # MultipleResultsFound here. Most-recent-first so a stale leftover never
    # shadows a genuinely new trigger.
    result = await db.execute(
        select(SosSession)
        .where(SosSession.user_id == user_id, SosSession.status == "active")
        .order_by(SosSession.created_at.desc())
    )
    return result.scalars().first()


async def _get_owned_session(
    db: AsyncSession, session_id: uuid.UUID, current_user: User
) -> SosSession:
    result = await db.execute(select(SosSession).where(SosSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SOS session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not the owner of this SOS session")
    return session


async def _maybe_auto_ban(db: AsyncSession, user: User) -> None:
    """Suspend the account once it crosses FALSE_ALARM_BAN_THRESHOLD
    false-alarm outcomes. "test" outcomes never count toward this — they're
    an expected, allowed way to try the feature."""
    if user.is_banned:
        return

    count = (
        await db.execute(
            select(func.count())
            .select_from(SosSession)
            .where(SosSession.user_id == user.id, SosSession.outcome == "false_alarm")
        )
    ).scalar_one()

    if count >= FALSE_ALARM_BAN_THRESHOLD:
        user.is_banned = True
        user.banned_at = datetime.now(UTC)
        user.ban_reason = f"Automatically suspended after {count} false alerts."
        await db.commit()


@router.post("", response_model=SosSessionRead, status_code=status.HTTP_201_CREATED)
async def trigger_sos(
    body: SosTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SosSessionRead:
    if current_user.is_banned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Your account is suspended for repeated false alerts. "
            f"To appeal, contact {SUPPORT_EMAIL}.",
        )

    # Guard against duplicate concurrent sessions (double-click, multiple
    # tabs, a network retry) — nothing else stopped a user from ending up
    # with two "active" sessions, which would show as duplicate entries on
    # /nearby and leave it ambiguous which one to resolve. Idempotent: just
    # hand back the existing active session instead of creating another.
    existing = await _get_active_session_for_user(db, current_user.id)
    if existing is not None:
        row = await _get_session_row(db, existing.id)
        return _to_read(*row)

    session = SosSession(
        user_id=current_user.id, status="active", location=_point(body.lat, body.lng)
    )
    db.add(session)
    await db.commit()
    row = await _get_session_row(db, session.id)
    result = _to_read(*row)

    # Broadcast-to-all, trigger-only push (no radius targeting yet — there's
    # no mechanism tracking a responder's current location outside their own
    # SOS sessions). One BackgroundTask per subscriber: pywebpush.webpush()
    # is a blocking call, and Starlette offloads each task to the thread
    # pool independently, so one slow/dead subscription can't stall others.
    if settings.VAPID_PRIVATE_KEY:
        subs = (await db.execute(select(PushSubscription))).scalars().all()
        payload = json.dumps(
            {
                "title": "SOS Alert",
                "body": "Someone nearby triggered an SOS.",
                "session_id": str(session.id),
            }
        )
        for sub in subs:
            background_tasks.add_task(send_push, sub, payload)

    return result


@router.post("/{session_id}/location", response_model=SosSessionRead)
async def update_sos_location(
    session_id: uuid.UUID,
    body: SosLocationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SosSessionRead:
    await _get_owned_session(db, session_id, current_user)

    # Single conditional UPDATE instead of a separate read-then-write: two
    # overlapping requests for the same session (a double-tap, a retried
    # request) can no longer both pass a status check and then race to write
    # — whichever commits first "wins" the active row, and the other gets a
    # clean 409 from rowcount==0 instead of piling up behind a row lock.
    exec_result = await db.execute(
        update(SosSession)
        .where(SosSession.id == session_id, SosSession.status == "active")
        .values(location=_point(body.lat, body.lng))
    )
    await db.commit()
    if exec_result.rowcount == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "SOS session is not active")

    row = await _get_session_row(db, session_id)
    result = _to_read(*row)
    await sos_ws_manager.broadcast(
        session_id,
        {"type": "location", "lat": result.lat, "lng": result.lng, "updated_at": result.updated_at.isoformat()},
    )
    return result


@router.post("/{session_id}/resolve", response_model=SosSessionRead)
async def resolve_sos(
    session_id: uuid.UUID,
    body: SosResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SosSessionRead:
    await _get_owned_session(db, session_id, current_user)

    resolved_at = datetime.now(UTC)
    exec_result = await db.execute(
        update(SosSession)
        .where(SosSession.id == session_id, SosSession.status == "active")
        .values(status="resolved", outcome=body.outcome, resolved_at=resolved_at)
    )
    await db.commit()
    if exec_result.rowcount == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "SOS session is not active")

    if body.outcome == "false_alarm":
        await _maybe_auto_ban(db, current_user)

    row = await _get_session_row(db, session_id)
    result = _to_read(*row)
    await sos_ws_manager.broadcast(
        session_id,
        {
            "type": "resolved",
            "outcome": result.outcome,
            "resolved_at": result.resolved_at.isoformat() if result.resolved_at else None,
        },
    )
    await sos_ws_manager.close_all(session_id)
    return result


@router.get("/nearby", response_model=list[NearbySosSession])
async def nearby_sos_sessions(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=5.0, gt=0, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NearbySosSession]:
    origin = _point(lat, lng)
    distance = func.ST_Distance(SosSession.location, origin).label("distance_meters")
    stmt = (
        select(
            SosSession,
            func.ST_Y(cast(SosSession.location, _GEOMETRY_POINT)).label("lat"),
            func.ST_X(cast(SosSession.location, _GEOMETRY_POINT)).label("lng"),
            User.display_name,
            User.phone_number,
            User.avatar_url,
            distance,
        )
        .join(User, User.id == SosSession.user_id)
        .where(SosSession.status == "active")
        .where(func.ST_DWithin(SosSession.location, origin, radius_km * 1000))
        .order_by(distance)
    )
    rows = (await db.execute(stmt)).all()
    return [
        NearbySosSession(
            **_to_read(session, lat_, lng_, display_name, phone_number, avatar_url).model_dump(),
            distance_meters=dist,
        )
        for session, lat_, lng_, display_name, phone_number, avatar_url, dist in rows
    ]


@router.get("/active", response_model=SosSessionRead | None)
async def get_active_sos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SosSessionRead | None:
    """The current user's own active session, if any — lets the dashboard
    restore state on page load instead of only knowing about a session it
    just created client-side (e.g. after a tab close/reopen)."""
    existing = await _get_active_session_for_user(db, current_user.id)
    if existing is None:
        return None
    row = await _get_session_row(db, existing.id)
    return _to_read(*row)


# Declared after /nearby and /active on purpose — a literal path must be
# matched before a same-method path-param route, or a request to those
# would instead be captured here as session_id="nearby"/"active" and fail
# UUID validation with a 422.
@router.get("/{session_id}", response_model=SosSessionRead)
async def get_sos(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SosSessionRead:
    # Any authenticated user may fetch any session (same openness as
    # /sos/nearby and the WS route — no responder/KYC tier exists yet).
    row = await _get_session_row(db, session_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SOS session not found")
    return _to_read(*row)
