"""
Bezalel.AI — In-memory IP-based rate-limiting middleware.

Tracks request counts per IP address in a dictionary and rejects
requests that exceed the configured threshold within the sliding window.

Default limits:
  - ``/api/auth/login`` : 5 requests / minute
  - Everything else     : 60 requests / minute

The store is periodically pruned to avoid unbounded memory growth.
"""

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# ── Configuration ────────────────────────────────────────────────────────
# Maps path prefixes to (max_requests, window_seconds).
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/auth/login": (5, 60),
    "/api/auth/verify-otp": (5, 60),
}
DEFAULT_RATE_LIMIT: tuple[int, int] = (60, 60)  # 60 req / 60 s

# ── In-memory store ─────────────────────────────────────────────────────
# key = (ip, route_key) -> list of timestamps
_request_log: dict[tuple[str, str], list[float]] = defaultdict(list)
_PRUNE_INTERVAL = 300  # seconds between full prune passes
_last_prune: float = 0.0


def _get_client_ip(request: Request) -> str:
    """Extract the client IP, preferring X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _route_key(path: str) -> str:
    """Return the most specific rate-limit key that matches ``path``."""
    for prefix in RATE_LIMITS:
        if path.startswith(prefix):
            return prefix
    return "__default__"


def _prune_store() -> None:
    """Remove stale entries older than the largest configured window."""
    global _last_prune
    now = time.time()
    if now - _last_prune < _PRUNE_INTERVAL:
        return
    _last_prune = now
    max_window = max(w for _, w in list(RATE_LIMITS.values()) + [DEFAULT_RATE_LIMIT])
    cutoff = now - max_window
    keys_to_delete: list[tuple[str, str]] = []
    for key, timestamps in _request_log.items():
        _request_log[key] = [t for t in timestamps if t > cutoff]
        if not _request_log[key]:
            keys_to_delete.append(key)
    for key in keys_to_delete:
        del _request_log[key]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that enforces per-IP request rate limits.

    Attach to the FastAPI app::

        app.add_middleware(RateLimitMiddleware)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = _get_client_ip(request)
        path = request.url.path
        rkey = _route_key(path)
        max_requests, window = RATE_LIMITS.get(rkey, DEFAULT_RATE_LIMIT)

        now = time.time()
        store_key = (ip, rkey)

        # Trim timestamps outside the current window.
        _request_log[store_key] = [
            t for t in _request_log[store_key] if t > now - window
        ]

        if len(_request_log[store_key]) >= max_requests:
            retry_after = int(window - (now - _request_log[store_key][0]))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        _request_log[store_key].append(now)

        # Periodically prune the global store.
        _prune_store()

        return await call_next(request)
