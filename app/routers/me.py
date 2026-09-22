from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UpdateProfileRequest, UserRead

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    first_time = current_user.consent_accepted_at is None
    if first_time and not body.accept_consent:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You must accept the terms to continue.",
        )

    current_user.display_name = body.display_name
    if body.phone_number:
        current_user.phone_number = body.phone_number
    if body.avatar_url:
        current_user.avatar_url = body.avatar_url
    if body.default_radius_km is not None:
        current_user.default_radius_km = body.default_radius_km
    if first_time:
        current_user.consent_accepted_at = datetime.now(UTC)

    # No db.refresh() needed: expire_on_commit=False (see db/session.py) means
    # current_user keeps every attribute we just set in Python above, and
    # nothing here is DB-generated — a refresh would just be an extra
    # round-trip that occasionally races Supabase's pooler badly enough to
    # raise "Could not refresh instance" (see contacts.py's add_contact for
    # the same fix applied to a case that actually hit this in testing).
    await db.commit()
    return current_user
