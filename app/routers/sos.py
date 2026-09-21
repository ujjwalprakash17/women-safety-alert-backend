import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
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
        )
        .where(SosSession.id == session_id)
        # expire_on_commit=False means an already identity-mapped instance
        # won't otherwise pick up attributes written by the just-committed flush.
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).one_or_none()


def _to_read(session: SosSession, lat: float, lng: float) -> SosSessionRead:
    return SosSessionRead(
        id=session.id,
        user_id=session.user_id,
        status=session.status,
        outcome=session.outcome,
        lat=lat,
        lng=lng,
        created_at=session.created_at,
        updated_at=session.updated_at,
        resolved_at=session.resolved_at,
    )


async def _get_owned_active_session(
    db: AsyncSession, session_id: uuid.UUID, current_user: User
) -> SosSession:
    result = await db.execute(select(SosSession).where(SosSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SOS session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not the owner of this SOS session")
    if session.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "SOS session is not active")
    return session


@router.post("", response_model=SosSessionRead, status_code=status.HTTP_201_CREATED)
async def trigger_sos(
    body: SosTriggerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SosSessionRead:
    session = SosSession(
        user_id=current_user.id, status="active", location=_point(body.lat, body.lng)
    )
    db.add(session)
    await db.commit()
    row = await _get_session_row(db, session.id)
    return _to_read(*row)


@router.post("/{session_id}/location", response_model=SosSessionRead)
async def update_sos_location(
    session_id: uuid.UUID,
    body: SosLocationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SosSessionRead:
    session = await _get_owned_active_session(db, session_id, current_user)
    session.location = _point(body.lat, body.lng)
    await db.commit()
    row = await _get_session_row(db, session_id)
    return _to_read(*row)


@router.post("/{session_id}/resolve", response_model=SosSessionRead)
async def resolve_sos(
    session_id: uuid.UUID,
    body: SosResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SosSessionRead:
    session = await _get_owned_active_session(db, session_id, current_user)
    session.status = "resolved"
    session.outcome = body.outcome
    session.resolved_at = datetime.now(UTC)
    await db.commit()
    row = await _get_session_row(db, session_id)
    return _to_read(*row)


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
            distance,
        )
        .where(SosSession.status == "active")
        .where(func.ST_DWithin(SosSession.location, origin, radius_km * 1000))
        .order_by(distance)
    )
    rows = (await db.execute(stmt)).all()
    return [
        NearbySosSession(**_to_read(session, lat_, lng_).model_dump(), distance_meters=dist)
        for session, lat_, lng_, dist in rows
    ]
