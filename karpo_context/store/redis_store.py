"""Redis-backed implementation of ContextStore."""
from __future__ import annotations

import json
import ssl
from typing import Any

from redis.asyncio import Redis

from karpo_context.models import ConversationContext
from karpo_context.store.base import ContextStore


class RedisContextStore(ContextStore):
    """Stores conversation context as JSON strings in Redis."""

    def __init__(
        self,
        redis_client: Redis,
        prefix: str = "karpo:ctx",
        ttl_seconds: int = 7 * 24 * 3600,
    ) -> None:
        self._redis = redis_client
        self._prefix = prefix
        self._ttl_seconds = ttl_seconds

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        prefix: str = "karpo:ctx",
        ttl_seconds: int = 7 * 24 * 3600,
        ssl_cert_reqs: str | None = None,
        **redis_kwargs: Any,
    ) -> RedisContextStore:
        """Create a store from a Redis URL.

        Supports ``redis://`` and ``rediss://`` (TLS) schemes.
        For AWS ElastiCache, use the ``rediss://`` endpoint directly.

        Args:
            url: Redis connection URL, e.g.
                ``rediss://master.my-cache.xxx.use1.cache.amazonaws.com:6379``
            prefix: Key prefix for Redis keys.
            ttl_seconds: Time-to-live for stored contexts.
            ssl_cert_reqs: SSL certificate verification mode. Pass ``"none"``
                to skip certificate verification (useful for ElastiCache
                endpoints with self-signed certs). Defaults to ``None``
                which uses the system default.
            **redis_kwargs: Extra keyword arguments forwarded to
                ``Redis.from_url()``, e.g. ``password``, ``decode_responses``.
        """
        kwargs: dict[str, Any] = {**redis_kwargs}

        if url.startswith("rediss://"):
            ssl_ctx = ssl.create_default_context()
            if ssl_cert_reqs == "none":
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
            kwargs.setdefault("ssl", True)
            kwargs.setdefault("ssl_context", ssl_ctx)

        client = Redis.from_url(url, **kwargs)
        return cls(client, prefix=prefix, ttl_seconds=ttl_seconds)

    async def close(self) -> None:
        """Close the underlying Redis connection."""
        await self._redis.aclose()

    def _key(self, conversation_id: int) -> str:
        return f"{self._prefix}:{conversation_id}"

    async def get(self, conversation_id: int) -> ConversationContext | None:
        raw = await self._redis.get(self._key(conversation_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return ConversationContext.from_dict(data)

    async def save(self, context: ConversationContext) -> None:
        key = self._key(context.conversation_id)
        data = json.dumps(context.to_dict())
        await self._redis.set(key, data, ex=self._ttl_seconds)

    async def delete(self, conversation_id: int) -> None:
        await self._redis.delete(self._key(conversation_id))
