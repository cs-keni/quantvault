from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.dependencies import CurrentUser
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead

router = APIRouter()


def _issue_token_pair(user_id: UUID) -> TokenResponse:
    subject = str(user_id)
    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    user = await db.scalar(select(User).where(User.email == email))
    return user


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    """Create an account. Emails are stored lowercased and are unique; duplicates -> 409.

    Returns the created user (not a token pair) — the client follows up with
    `POST /auth/login` to authenticate, keeping "create a resource" and
    "establish a session" as separate, individually-testable concerns.
    """
    email = payload.email.lower()
    if await _get_user_by_email(db, email) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="An account with this email already exists"
        )

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        # Two concurrent registrations for the same email both pass the check
        # above, then race to commit — the loser hits `users.email`'s unique
        # constraint. Translate that into the same 409 the check above would
        # have raised, instead of letting it surface as a raw 500.
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="An account with this email already exists"
        ) from exc
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> TokenResponse:
    """Exchange email + password for an access/refresh token pair.

    Returns the same 401 for "no such email" and "wrong password" — telling
    callers which one is true would let them enumerate registered emails.
    """
    user = await _get_user_by_email(db, payload.email.lower())
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="This account has been deactivated")

    return _issue_token_pair(user.id)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser) -> User:
    """Return the authenticated user's public profile for frontend hydration."""
    return current_user


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> TokenResponse:
    """Exchange a valid, non-expired refresh token for a brand new access/refresh pair.

    No server-side revocation list exists (stateless JWTs — see `security.py`),
    so refresh tokens aren't rotated/blacklisted on use; each one stays valid
    until its own expiry regardless of how many times it's exchanged. That's
    the standard tradeoff for a stateless design and is fine for this project's
    threat model — a persistent token store would be the upgrade path if this
    ever needed to support "log out everywhere"/breach revocation.
    """
    try:
        user_id = decode_token(payload.refresh_token, "refresh")
        user_uuid = UUID(user_id)
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        ) from exc

    user = await db.get(User, user_uuid)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    return _issue_token_pair(user.id)
