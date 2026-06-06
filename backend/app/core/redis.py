import redis.asyncio

from app.core.config import settings

redis_client: redis.asyncio.Redis = redis.asyncio.Redis.from_url(
    settings.REDIS_URL, decode_responses=False
)


async def get_redis() -> redis.asyncio.Redis:
    """FastAPI dependency yielding the shared Redis client."""
    return redis_client
