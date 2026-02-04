"""Tests for karpo_context.store layer."""
import json
from datetime import datetime, timezone

import pytest
import fakeredis.aioredis


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis()


class TestContextStoreABC:
    def test_cannot_instantiate(self):
        from karpo_context.store.base import ContextStore

        with pytest.raises(TypeError):
            ContextStore()

    def test_has_abstract_methods(self):
        from karpo_context.store.base import ContextStore

        assert hasattr(ContextStore, "get")
        assert hasattr(ContextStore, "save")
        assert hasattr(ContextStore, "delete")


class TestRedisContextStore:
    def test_is_subclass_of_context_store(self):
        from karpo_context.store.base import ContextStore
        from karpo_context.store.redis_store import RedisContextStore

        assert issubclass(RedisContextStore, ContextStore)

    async def test_get_nonexistent_returns_none(self, redis_client):
        from karpo_context.store.redis_store import RedisContextStore

        store = RedisContextStore(redis_client)
        result = await store.get(999)
        assert result is None

    async def test_save_and_get_roundtrip(self, redis_client):
        from karpo_context.models import ConversationContext
        from karpo_context.store.redis_store import RedisContextStore

        store = RedisContextStore(redis_client)
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(conversation_id=1, created_at=now, updated_at=now)
        await store.save(ctx)
        loaded = await store.get(1)
        assert loaded is not None
        assert loaded.conversation_id == 1

    async def test_save_and_get_with_messages(self, redis_client):
        from karpo_context.models import ChatMessage, ConversationContext
        from karpo_context.store.redis_store import RedisContextStore

        store = RedisContextStore(redis_client)
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(
            conversation_id=2,
            messages=[ChatMessage(role="user", content="Hello", created_at=now)],
            created_at=now,
            updated_at=now,
            message_count=1,
        )
        await store.save(ctx)
        loaded = await store.get(2)
        assert loaded is not None
        assert len(loaded.messages) == 1
        assert loaded.messages[0].content == "Hello"

    async def test_overwrite_existing(self, redis_client):
        from karpo_context.models import ConversationContext
        from karpo_context.store.redis_store import RedisContextStore

        store = RedisContextStore(redis_client)
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(
            conversation_id=3, created_at=now, updated_at=now, phase="idle"
        )
        await store.save(ctx)
        ctx.phase = "confirming"
        await store.save(ctx)
        loaded = await store.get(3)
        assert loaded is not None
        assert loaded.phase == "confirming"

    async def test_delete(self, redis_client):
        from karpo_context.models import ConversationContext
        from karpo_context.store.redis_store import RedisContextStore

        store = RedisContextStore(redis_client)
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(conversation_id=4, created_at=now, updated_at=now)
        await store.save(ctx)
        await store.delete(4)
        result = await store.get(4)
        assert result is None

    async def test_delete_nonexistent_is_noop(self, redis_client):
        from karpo_context.store.redis_store import RedisContextStore

        store = RedisContextStore(redis_client)
        await store.delete(9999)  # Should not raise

    async def test_key_format(self, redis_client):
        from karpo_context.models import ConversationContext
        from karpo_context.store.redis_store import RedisContextStore

        store = RedisContextStore(redis_client, prefix="test:ctx")
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(conversation_id=5, created_at=now, updated_at=now)
        await store.save(ctx)
        raw = await redis_client.get("test:ctx:5")
        assert raw is not None
        data = json.loads(raw)
        assert data["conversation_id"] == 5

    async def test_ttl_is_set(self, redis_client):
        from karpo_context.models import ConversationContext
        from karpo_context.store.redis_store import RedisContextStore

        store = RedisContextStore(redis_client, ttl_seconds=3600)
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(conversation_id=6, created_at=now, updated_at=now)
        await store.save(ctx)
        ttl = await redis_client.ttl("karpo:ctx:6")
        assert ttl > 0
        assert ttl <= 3600

    async def test_default_prefix_and_ttl(self, redis_client):
        from karpo_context.models import ConversationContext
        from karpo_context.store.redis_store import RedisContextStore

        store = RedisContextStore(redis_client)
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(conversation_id=7, created_at=now, updated_at=now)
        await store.save(ctx)
        raw = await redis_client.get("karpo:ctx:7")
        assert raw is not None
        ttl = await redis_client.ttl("karpo:ctx:7")
        assert ttl > 0
        assert ttl <= 7 * 24 * 3600
