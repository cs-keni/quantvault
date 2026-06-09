import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Supabase session pooler uses a self-signed CA in its certificate chain,
# so standard cert verification fails. Use SSL without hostname/cert checks.
if settings.ENVIRONMENT == "production":
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE
    _connect_args: dict[str, object] = {"ssl": _ssl_ctx}
else:
    _connect_args = {}

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    """Declarative base shared by every SQLAlchemy ORM model."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with AsyncSessionLocal() as session:
        yield session
