import uuid

import jwt
from fastapi import Depends, HTTPException, Query, WebSocket, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_maker, get_db
from app.models.user import User

_bearer_scheme = HTTPBearer()

# PyJWKClient caches Supabase's public signing keys internally (10-minute edge
# cache upstream too), so no extra caching layer is needed at this scale.
_jwk_client = jwt.PyJWKClient(settings.SUPABASE_JWKS_URL)


def _decode_supabase_jwt(token: str) -> dict:
    """Verify a Supabase-issued JWT.

    Supabase's `aud` claim is always the literal string "authenticated" (not the
    project URL). New projects sign with asymmetric ES256 keys (verified via the
    JWKS endpoint below); older projects may still use a legacy HS256 shared
    secret — check Project Settings > API > JWT Settings to see which mode is
    active, and set SUPABASE_JWT_SECRET in .env if it's the legacy one.
    """
    try:
        if settings.SUPABASE_JWT_SECRET:
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience=settings.SUPABASE_JWT_AUD,
            )

        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience=settings.SUPABASE_JWT_AUD,
            issuer=f"{settings.SUPABASE_URL}/auth/v1",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        ) from exc


async def _authenticate_supabase_token(token: str, db: AsyncSession) -> User:
    payload = _decode_supabase_jwt(token)

    supabase_user_id = uuid.UUID(payload["sub"])
    # Which claim is populated depends on the sign-in provider: phone for
    # phone-OTP, email for Google OAuth. At least one must be present.
    phone_number = payload.get("phone") or None
    email = payload.get("email") or None
    if not phone_number and not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has neither a phone nor an email claim.",
        )

    result = await db.execute(
        select(User).where(User.supabase_user_id == supabase_user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            supabase_user_id=supabase_user_id,
            phone_number=phone_number,
            email=email,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _authenticate_supabase_token(credentials.credentials, db)


async def get_current_user_ws(
    websocket: WebSocket, token: str | None = Query(default=None)
) -> User:
    """WebSocket counterpart of get_current_user.

    Browsers can't set custom headers on a WebSocket handshake, so the token
    travels as a query param instead — this can land in access logs; a
    short-lived one-time ticket would avoid that, but isn't needed yet.

    Deliberately does NOT use the `get_db` dependency: that dependency's
    AsyncExitStack lifetime lasts until the endpoint coroutine returns, which
    for a WebSocket is the whole connection duration — that would hold a
    pooled DB connection checked out for as long as someone is watching an
    SOS session. A short-lived session is used instead, closed immediately.
    """
    if not token:
        raise WebSocketException(code=4401, reason="Missing token")
    async with async_session_maker() as db:
        try:
            return await _authenticate_supabase_token(token, db)
        except HTTPException as exc:
            raise WebSocketException(code=4401, reason=str(exc.detail)) from exc
