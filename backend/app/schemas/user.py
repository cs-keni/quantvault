from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Registration payload. The plaintext `password` is hashed before storage and never persisted."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class UserRead(BaseModel):
    """Public user representation returned by the API — omits `hashed_password`."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    default_portfolio_id: UUID | None
    created_at: datetime
