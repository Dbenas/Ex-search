import hmac
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from curator.config import Settings, get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    api_key: Annotated[str | None, Depends(_api_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Constant-time API key check. Local runs without configured keys are open."""
    if not settings.api_keys:
        if settings.environment == "production":
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "API keys not configured")
        return "local"
    if api_key and any(
        hmac.compare_digest(api_key, k.get_secret_value()) for k in settings.api_keys
    ):
        return api_key[:6]
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing API key")


class RateLimiter:
    """Sliding-window limiter per client.

    In-process on purpose for the prototype; in production this moves to Cloud Armor.
    """

    def __init__(self, per_minute: int) -> None:
        self._limit = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client: str) -> None:
        now = time.monotonic()
        window = self._hits[client]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self._limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "rate limit exceeded",
                headers={"Retry-After": str(int(60 - (now - window[0])) + 1)},
            )
        window.append(now)


def client_key(request: Request, api_key: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{api_key}:{host}"
