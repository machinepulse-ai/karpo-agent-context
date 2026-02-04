"""Tests for karpo_context.manager.ContextManager."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from karpo_context.compaction.message_count import MessageCountTrigger
from karpo_context.compaction.summarizer import LLMSummarizer
from karpo_context.models import ChatMessage, ConversationContext
from karpo_context.store.redis_store import RedisContextStore


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def store(redis_client):
    return RedisContextStore(redis_client)


@pytest.fixture
def llm_mock():
    return AsyncMock(return_value="Compacted summary.")


@pytest.fixture
def trigger():
    return MessageCountTrigger(threshold=5)


@pytest.fixture
def summarizer(llm_mock):
    return LLMSummarizer(llm_callable=llm_mock)


class TestLoad:
    async def test_load_nonexistent_creates_new(self, store):
        from karpo_context.manager import ContextManager

        manager = ContextManager(store=store)
        ctx = await manager.load(42)
        assert ctx.conversation_id == 42
        assert ctx.messages == []
        assert ctx.phase == "idle"
        assert ctx.created_at is not None
        assert ctx.updated_at is not None

    async def test_load_existing_returns_stored(self, store):
        from karpo_context.manager import ContextManager

        now = datetime.now(timezone.utc)
        ctx = ConversationContext(
            conversation_id=1, created_at=now, updated_at=now, phase="confirming"
        )
        await store.save(ctx)

        manager = ContextManager(store=store)
        loaded = await manager.load(1)
        assert loaded.conversation_id == 1
        assert loaded.phase == "confirming"


class TestSave:
    async def test_save_stores_context(self, store):
        from karpo_context.manager import ContextManager

        manager = ContextManager(store=store)
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(conversation_id=10, created_at=now, updated_at=now)
        await manager.save(ctx)
        loaded = await store.get(10)
        assert loaded is not None
        assert loaded.conversation_id == 10

    async def test_no_compaction_below_threshold(self, store, trigger, summarizer):
        from karpo_context.manager import ContextManager

        manager = ContextManager(
            store=store, trigger=trigger, summarizer=summarizer
        )
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(
            conversation_id=11,
            messages=[
                ChatMessage(role="user", content=f"msg{i}", created_at=now)
                for i in range(3)
            ],
            created_at=now,
            updated_at=now,
            message_count=3,
        )
        await manager.save(ctx)
        loaded = await store.get(11)
        assert len(loaded.messages) == 3
        assert loaded.summary is None

    async def test_compaction_triggered_when_exceeded(
        self, store, trigger, summarizer
    ):
        from karpo_context.manager import ContextManager

        manager = ContextManager(
            store=store, trigger=trigger, summarizer=summarizer, keep_recent=3
        )
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(
            conversation_id=12,
            messages=[
                ChatMessage(role="user", content=f"msg{i}", created_at=now)
                for i in range(8)
            ],
            created_at=now,
            updated_at=now,
            message_count=8,
        )
        await manager.save(ctx)
        loaded = await store.get(12)
        assert loaded.summary == "Compacted summary."
        assert len(loaded.messages) == 3
        assert loaded.messages[0].content == "msg5"
        assert loaded.messages[1].content == "msg6"
        assert loaded.messages[2].content == "msg7"
        assert loaded.message_count == 3


class TestAppendMessage:
    async def test_append_to_nonexistent_creates_and_appends(self, store):
        from karpo_context.manager import ContextManager

        manager = ContextManager(store=store)
        now = datetime.now(timezone.utc)
        msg = ChatMessage(role="user", content="Hello", created_at=now)
        ctx = await manager.append_message(100, msg)
        assert len(ctx.messages) == 1
        assert ctx.messages[0].content == "Hello"
        assert ctx.message_count == 1

    async def test_append_to_existing(self, store):
        from karpo_context.manager import ContextManager

        manager = ContextManager(store=store)
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(
            conversation_id=101,
            messages=[ChatMessage(role="user", content="First", created_at=now)],
            created_at=now,
            updated_at=now,
            message_count=1,
        )
        await store.save(ctx)

        msg = ChatMessage(role="assistant", content="Second", created_at=now)
        updated = await manager.append_message(101, msg)
        assert len(updated.messages) == 2
        assert updated.message_count == 2

    async def test_append_updates_updated_at(self, store):
        from karpo_context.manager import ContextManager

        manager = ContextManager(store=store)
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(
            conversation_id=102, created_at=now, updated_at=now
        )
        await store.save(ctx)

        msg = ChatMessage(role="user", content="Hey", created_at=now)
        updated = await manager.append_message(102, msg)
        assert updated.updated_at >= now


class TestWithoutOptionalDeps:
    async def test_works_without_trigger_and_summarizer(self, store):
        from karpo_context.manager import ContextManager

        manager = ContextManager(store=store)
        now = datetime.now(timezone.utc)
        ctx = ConversationContext(
            conversation_id=200,
            messages=[
                ChatMessage(role="user", content=f"msg{i}", created_at=now)
                for i in range(100)
            ],
            created_at=now,
            updated_at=now,
            message_count=100,
        )
        await manager.save(ctx)
        loaded = await store.get(200)
        assert len(loaded.messages) == 100
        assert loaded.summary is None
