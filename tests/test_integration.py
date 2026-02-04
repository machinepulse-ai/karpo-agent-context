"""Integration tests for the full conversation lifecycle."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from karpo_context.compaction.message_count import MessageCountTrigger
from karpo_context.compaction.summarizer import LLMSummarizer
from karpo_context.manager import ContextManager
from karpo_context.models import ChatMessage, ConversationContext, ToolCallRecord
from karpo_context.store.redis_store import RedisContextStore


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def store(redis_client):
    return RedisContextStore(redis_client)


@pytest.fixture
def llm_mock():
    return AsyncMock(return_value="Summary of the conversation so far.")


@pytest.fixture
def manager(store, llm_mock):
    return ContextManager(
        store=store,
        trigger=MessageCountTrigger(threshold=5),
        summarizer=LLMSummarizer(llm_callable=llm_mock),
        keep_recent=3,
    )


class TestFullConversationLifecycle:
    async def test_create_append_compact_continue(self, manager, store):
        """Full lifecycle: create -> append messages -> trigger compaction -> continue."""
        now = datetime.now(timezone.utc)

        # Create conversation by appending first message
        ctx = await manager.append_message(
            1, ChatMessage(role="user", content="Hello", created_at=now)
        )
        assert ctx.conversation_id == 1
        assert len(ctx.messages) == 1

        # Append more messages (total 5, still at threshold — no compaction)
        for i in range(4):
            role = "assistant" if i % 2 == 0 else "user"
            ctx = await manager.append_message(
                1, ChatMessage(role=role, content=f"msg{i + 2}", created_at=now)
            )
        assert len(ctx.messages) == 5
        assert ctx.summary is None

        # Append one more (total 6, exceeds threshold=5 -> compaction)
        ctx = await manager.append_message(
            1, ChatMessage(role="user", content="trigger compaction", created_at=now)
        )
        assert ctx.summary == "Summary of the conversation so far."
        assert len(ctx.messages) == 3  # keep_recent=3

        # Continue after compaction
        ctx = await manager.append_message(
            1, ChatMessage(role="assistant", content="After compaction", created_at=now)
        )
        assert len(ctx.messages) == 4
        assert ctx.summary == "Summary of the conversation so far."

        # Verify persistence — reload from store
        loaded = await store.get(1)
        assert loaded is not None
        assert loaded.summary == "Summary of the conversation so far."
        assert len(loaded.messages) == 4


class TestAllFieldsRoundtrip:
    async def test_context_with_all_fields(self, store):
        """Verify a fully-populated context survives a Redis roundtrip."""
        now = datetime.now(timezone.utc)
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "search", "arguments": '{"q":"test"}'},
            }
        ]
        ctx = ConversationContext(
            conversation_id=42,
            messages=[
                ChatMessage(role="user", content="Hi", created_at=now),
                ChatMessage(
                    role="assistant",
                    content=None,
                    created_at=now,
                    tool_calls=tool_calls,
                ),
                ChatMessage(
                    role="tool",
                    content='{"result": "found"}',
                    created_at=now,
                    tool_call_id="call_1",
                ),
            ],
            summary="Previous summary",
            persona={"name": "Agent", "style": "helpful"},
            loaded_tools=["search", "calculate"],
            loaded_skills=["chat", "code"],
            tool_call_history=[
                ToolCallRecord(
                    tool_name="search",
                    arguments={"q": "test"},
                    result="found",
                    called_at=now,
                    duration_ms=120,
                )
            ],
            phase="executing",
            slots={"query": "test", "confirmed": True},
            missing_slots=["location"],
            intent="search_web",
            created_at=now,
            updated_at=now,
            message_count=3,
        )
        await store.save(ctx)
        loaded = await store.get(42)

        assert loaded is not None
        assert loaded.conversation_id == 42
        assert len(loaded.messages) == 3
        assert loaded.messages[1].tool_calls == tool_calls
        assert loaded.messages[2].tool_call_id == "call_1"
        assert loaded.summary == "Previous summary"
        assert loaded.persona == {"name": "Agent", "style": "helpful"}
        assert loaded.loaded_tools == ["search", "calculate"]
        assert loaded.loaded_skills == ["chat", "code"]
        assert len(loaded.tool_call_history) == 1
        assert loaded.tool_call_history[0].tool_name == "search"
        assert loaded.tool_call_history[0].duration_ms == 120
        assert loaded.phase == "executing"
        assert loaded.slots == {"query": "test", "confirmed": True}
        assert loaded.missing_slots == ["location"]
        assert loaded.intent == "search_web"
        assert loaded.message_count == 3


class TestDeleteAndReload:
    async def test_delete_and_reload_creates_fresh(self, store):
        """Deleting a context and re-loading should create a fresh one."""
        manager = ContextManager(store=store)
        now = datetime.now(timezone.utc)

        # Create and save
        ctx = await manager.append_message(
            50, ChatMessage(role="user", content="Hello", created_at=now)
        )
        assert len(ctx.messages) == 1

        # Delete
        await store.delete(50)

        # Reload — should be fresh
        ctx = await manager.load(50)
        assert ctx.conversation_id == 50
        assert ctx.messages == []
        assert ctx.summary is None
        assert ctx.message_count == 0
