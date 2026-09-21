import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = _decode_supabase_jwt(credentials.credentials)

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
