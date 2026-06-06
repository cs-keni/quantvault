from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Credentials payload for `POST /auth/login`."""

    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    """Payload for `POST /auth/refresh` — trades a valid refresh token for a new token pair."""

    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """JWT pair issued on login and renewed on refresh.

    `access_token` authenticates API requests (`Authorization: Bearer <token>`,
    short-lived); `refresh_token` is presented to `/auth/refresh` to mint a new
    pair once the access token expires (long-lived, used nowhere else).
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
