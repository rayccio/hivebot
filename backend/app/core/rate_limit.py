import time
from fastapi import Request, HTTPException, status
from ..services.redis_service import redis_service
from ..models.types import GlobalSettings
from ..core.config import settings

async def check_rate_limit(request: Request, limit_key: str = "default") -> None:
    """
    Rate limiting middleware based on IP address and a key (e.g., 'login').
    Uses Redis to store counters with expiration.
    Limits are read from global settings (cached for a short time).
    """
    # Get client IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host

    # Load current rate limit settings (could be cached)
    settings_data = settings.secrets.get("GLOBAL_SETTINGS")
    if settings_data:
        global_settings = GlobalSettings(**settings_data)
    else:
        global_settings = GlobalSettings()

    if not global_settings.rate_limit_enabled:
        return

    # Create Redis key: rate_limit:{key}:{client_ip}
    redis_key = f"rate_limit:{limit_key}:{client_ip}"
    now = int(time.time())

    # Get current count and expiry
    async with await redis_service.get_client() as redis:
        pipe = redis.pipeline()
        pipe.get(redis_key)
        pipe.ttl(redis_key)
        count_str, ttl = await pipe.execute()

    count = int(count_str) if count_str else 0

    if count >= global_settings.rate_limit_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )

    # Increment or set with expiry
    async with await redis_service.get_client() as redis:
        if count == 0:
            await redis.setex(redis_key, global_settings.rate_limit_period_seconds, 1)
        else:
            await redis.incr(redis_key)
