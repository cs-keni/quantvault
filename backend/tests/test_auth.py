import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.dependencies import get_current_user
from app.models.user import User
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

REGISTER_PAYLOAD = {
    "email": "rin@example.com",
    "password": "correcthorsebattery",
    "full_name": "Rin Tezuka",
}


def _expired_token(subject: str, token_type: str) -> str:
    """Hand-craft a JWT whose `exp` is already in the past.

    `create_access_token`/`create_refresh_token` always mint forward-looking
    expiries, so an expired token can only be produced by encoding one directly
    with the same secret/algorithm the app uses.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def _register_and_login(client: AsyncClient) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
    )
    tokens: dict[str, str] = response.json()
    return tokens


# --- POST /auth/register ---------------------------------------------------


async def test_register_creates_user(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "rin@example.com"
    assert body["full_name"] == "Rin Tezuka"
    assert body["is_active"] is True
    assert body["default_portfolio_id"] is None
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_normalizes_and_dedupes_email(client: AsyncClient) -> None:
    first = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "email": "RIN@EXAMPLE.COM", "full_name": "Someone Else"},
    )
    assert duplicate.status_code == 409


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register", json={**REGISTER_PAYLOAD, "password": "short"}
    )
    assert response.status_code == 422


async def test_register_rejects_invalid_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register", json={**REGISTER_PAYLOAD, "email": "not-an-email"}
    )
    assert response.status_code == 422


# --- POST /auth/login -------------------------------------------------------


async def test_login_returns_distinct_token_pair(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "RIN@example.com", "password": REGISTER_PAYLOAD["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]


async def test_login_rejects_wrong_password(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": "totally-wrong-password"},
    )
    assert response.status_code == 401


async def test_login_rejects_unknown_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )
    assert response.status_code == 401


async def test_login_rejects_deactivated_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = User(
        email="inactive@example.com",
        hashed_password=hash_password("whatever123"),
        full_name="Inactive User",
        is_active=False,
    )
    db_session.add(user)
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/login", json={"email": "inactive@example.com", "password": "whatever123"}
    )
    assert response.status_code == 403


# --- GET /auth/me -----------------------------------------------------------


async def test_get_me_returns_authenticated_user(client: AsyncClient) -> None:
    tokens = await _register_and_login(client)

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]
    assert body["full_name"] == REGISTER_PAYLOAD["full_name"]
    assert "hashed_password" not in body


async def test_get_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


# --- POST /auth/refresh ------------------------------------------------------


async def test_refresh_issues_new_token_pair(client: AsyncClient) -> None:
    tokens = await _register_and_login(client)

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["refresh_token"]


async def test_refresh_rejects_access_token(client: AsyncClient) -> None:
    tokens = await _register_and_login(client)

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert response.status_code == 401


async def test_refresh_rejects_expired_token(client: AsyncClient, db_session: AsyncSession) -> None:
    user = User(
        email="expired@example.com",
        hashed_password=hash_password("whatever123"),
        full_name="Expired",
    )
    db_session.add(user)
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": _expired_token(str(user.id), "refresh")},
    )
    assert response.status_code == 401


async def test_refresh_rejects_malformed_token(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt-at-all"})
    assert response.status_code == 401


async def test_refresh_rejects_unknown_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": create_refresh_token(str(uuid.uuid4()))}
    )
    assert response.status_code == 401


# --- get_current_user dependency --------------------------------------------
# Exercised directly: it's the auth boundary every future protected route sits
# behind, but Phase 1 ships no protected routes yet to drive it through `client`.


async def test_get_current_user_resolves_valid_access_token(db_session: AsyncSession) -> None:
    user = User(
        email="valid@example.com",
        hashed_password=hash_password("whatever123"),
        full_name="Valid User",
    )
    db_session.add(user)
    await db_session.flush()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_access_token(str(user.id))
    )
    resolved = await get_current_user(credentials, db_session)

    assert resolved.id == user.id


async def test_get_current_user_rejects_missing_credentials(db_session: AsyncSession) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(None, db_session)
    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_malformed_token(db_session: AsyncSession) -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="garbage-token")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials, db_session)
    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_refresh_token(db_session: AsyncSession) -> None:
    user = User(
        email="wrongtype@example.com",
        hashed_password=hash_password("whatever123"),
        full_name="Wrong Type",
    )
    db_session.add(user)
    await db_session.flush()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_refresh_token(str(user.id))
    )
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials, db_session)
    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_deactivated_user(db_session: AsyncSession) -> None:
    user = User(
        email="deactivated@example.com",
        hashed_password=hash_password("whatever123"),
        full_name="Deactivated User",
        is_active=False,
    )
    db_session.add(user)
    await db_session.flush()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_access_token(str(user.id))
    )
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials, db_session)
    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_unknown_user_id(db_session: AsyncSession) -> None:
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_access_token(str(uuid.uuid4()))
    )
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials, db_session)
    assert exc_info.value.status_code == 401
