"""Redis-backed implementation of ContextStore."""
import json

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
