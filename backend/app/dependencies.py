from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated `User` from an `Authorization: Bearer <access token>` header.

    Every failure mode — missing header, malformed/expired/wrong-type/bad-
    signature token, unknown user id, deactivated account — raises the same
    401, so the API never tells a caller *which* of those is true.
    """
    if credentials is None:
        raise _credentials_error()

    try:
        user_id = decode_token(credentials.credentials, "access")
        user_uuid = UUID(user_id)
    except (jwt.PyJWTError, ValueError) as exc:
        raise _credentials_error() from exc

    user = await db.get(User, user_uuid)
    if user is None or not user.is_active:
        raise _credentials_error()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
