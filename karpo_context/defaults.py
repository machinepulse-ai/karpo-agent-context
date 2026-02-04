"""Pre-configured defaults for karpo-context SDK."""
from __future__ import annotations

import os

from karpo_context.store.redis_store import RedisContextStore

CONTEXT_REDIS_URL = (
    "rediss://master.karpo-context-cache.wimmex.use1.cache.amazonaws.com:6379"
)


def create_context_store(
    *,
    url: str | None = None,
    prefix: str = "karpo:ctx",
    ttl_seconds: int = 7 * 24 * 3600,
) -> RedisContextStore:
    """Create a RedisContextStore with the default ElastiCache endpoint.

    Resolution order for the Redis URL:
      1. Explicit ``url`` parameter
      2. ``KARPO_CONTEXT_REDIS_URL`` environment variable
      3. Built-in default (AWS ElastiCache staging endpoint)

    Args:
        url: Override the Redis URL.
        prefix: Key prefix for Redis keys.
        ttl_seconds: Time-to-live for stored contexts.
    """
    resolved_url = url or os.environ.get("KARPO_CONTEXT_REDIS_URL") or CONTEXT_REDIS_URL
    return RedisContextStore.from_url(resolved_url, prefix=prefix, ttl_seconds=ttl_seconds)
