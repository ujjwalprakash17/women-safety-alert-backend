import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.trusted_contact import TrustedContact
from app.models.user import User
from app.schemas.trusted_contact import TrustedContactCreate, TrustedContactRead

router = APIRouter(prefix="/contacts", tags=["contacts"])

MAX_CONTACTS_PER_USER = 5


@router.get("", response_model=list[TrustedContactRead])
async def list_contacts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrustedContact]:
    result = await db.execute(
        select(TrustedContact)
        .where(TrustedContact.user_id == current_user.id)
        .order_by(TrustedContact.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=TrustedContactRead, status_code=status.HTTP_201_CREATED)
async def add_contact(
    body: TrustedContactCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrustedContact:
    count = (
        await db.execute(
            select(func.count())
            .select_from(TrustedContact)
            .where(TrustedContact.user_id == current_user.id)
        )
    ).scalar_one()
    if count >= MAX_CONTACTS_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Maximum of {MAX_CONTACTS_PER_USER} trusted contacts reached.",
        )

    contact = TrustedContact(
        user_id=current_user.id,
        name=body.name,
        phone_number=body.phone_number,
        relationship_label=body.relationship_label,
        # Set explicitly rather than relying on the column's server_default +
        # a post-commit db.refresh(): a refresh is a second round-trip that
        # occasionally raced Supabase's pooler badly enough to raise
        # "Could not refresh instance" (row not visible yet to the refresh
        # query's connection) — avoidable entirely since we don't need
        # anything else the database would generate for us here.
        created_at=datetime.now(UTC),
    )
    db.add(contact)
    await db.commit()
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(TrustedContact).where(
            TrustedContact.id == contact_id, TrustedContact.user_id == current_user.id
        )
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trusted contact not found")

    await db.delete(contact)
    await db.commit()
