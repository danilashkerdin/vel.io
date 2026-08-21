from slowapi import Limiter
from slowapi.util import get_remote_address

from config import settings

limiter = Limiter(key_func=get_remote_address)


def limit_rate(rate: str):
    """Rate-limit decorator that honours setting.RATELIMIT_ENABLED.

    When rate limiting is disabled (e.g. for e2e tests coming from a single
    local IP) the decorator becomes a no-op, so tests are never flaky due to
    the per-IP quota. Production keeps the default behaviour (enabled).
    """
    if not settings.RATELIMIT_ENABLED:
        return lambda func: func
    return limiter.limit(rate)