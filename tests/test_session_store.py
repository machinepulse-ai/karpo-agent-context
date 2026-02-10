"""Tests for SessionStateStore - Redis storage for SessionState."""
import json
from datetime import datetime, timezone

import pytest
import fakeredis.aioredis

from karpo_context.models import SessionState, ConversationSummary, ChatMessage


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis()


class TestSessionStateStore:
    """Tests for SessionStateStore with new key format."""

    def test_is_subclass_of_context_store(self):
        from karpo_context.store.base import ContextStore
        from karpo_context.store.session_store import SessionStateStore

        assert issubclass(SessionStateStore, ContextStore)

    async def test_get_nonexistent_returns_none(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        result = await store.get(999)
        assert result is None

    async def test_save_and_get_roundtrip(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=1,
            user_id="user-001",
            created_at=now,
            updated_at=now,
        )
        await store.save(session)
        loaded = await store.get(1)
        assert loaded is not None
        assert loaded.thread_id == 1
        assert loaded.user_id == "user-001"

    async def test_save_and_get_with_messages(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=2,
            user_id="user-001",
            created_at=now,
            updated_at=now,
        )
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        await store.save(session)
        loaded = await store.get(2)
        assert loaded is not None
        assert len(loaded.messages) == 2
        assert loaded.messages[0].content == "Hello"
        assert loaded.turn_count == 1

    async def test_save_and_get_with_summary(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        now = datetime.now(timezone.utc)
        summary = ConversationSummary(
            covers_until_turn=5,
            generated_at=now,
            user_intent="Plan Tokyo trip",
            key_entities={"destination": "Tokyo"},
            decisions_made=["March 1st departure"],
            pending_questions=["Need JR Pass?"],
        )
        session = SessionState(
            thread_id=3,
            user_id="user-001",
            created_at=now,
            updated_at=now,
            summary=summary,
            turn_count=5,
        )
        await store.save(session)
        loaded = await store.get(3)
        assert loaded is not None
        assert loaded.summary is not None
        assert loaded.summary.user_intent == "Plan Tokyo trip"
        assert loaded.summary.key_entities["destination"] == "Tokyo"

    async def test_key_format_uses_agent_name(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=100,
            user_id="user-001",
            created_at=now,
            updated_at=now,
        )
        await store.save(session)
        # Key format: ctx:{agent}:session:{thread_id}
        raw = await redis_client.get("ctx:travel:session:100")
        assert raw is not None
        data = json.loads(raw)
        assert data["thread_id"] == 100

    async def test_different_agents_have_separate_keys(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        travel_store = SessionStateStore(redis_client, agent_name="travel")
        dining_store = SessionStateStore(redis_client, agent_name="dining")
        now = datetime.now(timezone.utc)

        travel_session = SessionState(
            thread_id=1, user_id="user-001", created_at=now, updated_at=now
        )
        travel_session.add_message("user", "I want to go to Tokyo")
        await travel_store.save(travel_session)

        dining_session = SessionState(
            thread_id=1, user_id="user-001", created_at=now, updated_at=now
        )
        dining_session.add_message("user", "I want sushi")
        await dining_store.save(dining_session)

        loaded_travel = await travel_store.get(1)
        loaded_dining = await dining_store.get(1)

        assert loaded_travel.messages[0].content == "I want to go to Tokyo"
        assert loaded_dining.messages[0].content == "I want sushi"

    async def test_delete(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=4, user_id="user-001", created_at=now, updated_at=now
        )
        await store.save(session)
        await store.delete(4)
        result = await store.get(4)
        assert result is None

    async def test_ttl_is_set(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel", ttl_seconds=3600)
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=5, user_id="user-001", created_at=now, updated_at=now
        )
        await store.save(session)
        ttl = await redis_client.ttl("ctx:travel:session:5")
        assert ttl > 0
        assert ttl <= 3600


class TestToolResultOffloading:
    """Tests for tool result offloading storage."""

    async def test_save_tool_result(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        await store.save_tool_result(
            thread_id=1,
            call_id="call_abc123",
            result={"flights": [{"id": 1, "price": 500}]},
        )
        # Key format: ctx:{agent}:tool:{thread_id}:{call_id}
        raw = await redis_client.get("ctx:travel:tool:1:call_abc123")
        assert raw is not None
        data = json.loads(raw)
        assert data["flights"][0]["price"] == 500

    async def test_get_tool_result(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        await store.save_tool_result(
            thread_id=1,
            call_id="call_xyz789",
            result={"weather": "sunny", "temp": 25},
        )
        result = await store.get_tool_result(thread_id=1, call_id="call_xyz789")
        assert result is not None
        assert result["weather"] == "sunny"
        assert result["temp"] == 25

    async def test_get_nonexistent_tool_result_returns_none(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        result = await store.get_tool_result(thread_id=999, call_id="nonexistent")
        assert result is None

    async def test_tool_result_ttl(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel", ttl_seconds=3600)
        await store.save_tool_result(
            thread_id=1, call_id="call_ttl", result={"data": "test"}
        )
        ttl = await redis_client.ttl("ctx:travel:tool:1:call_ttl")
        assert ttl > 0
        assert ttl <= 3600


class TestErrorNotebook:
    """Tests for error notebook (sliding window storage)."""

    async def test_append_error(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        error = {
            "step": 3,
            "tool_name": "search_flights",
            "error_type": "APIError",
            "message": "Rate limit exceeded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await store.append_error(thread_id=1, error=error)
        errors = await store.get_errors(thread_id=1)
        assert len(errors) == 1
        assert errors[0]["tool_name"] == "search_flights"

    async def test_get_errors_returns_all(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        for i in range(5):
            await store.append_error(
                thread_id=1,
                error={"step": i, "message": f"Error {i}"},
            )
        errors = await store.get_errors(thread_id=1)
        assert len(errors) == 5

    async def test_errors_sliding_window_max_50(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel", error_max_count=50)
        for i in range(60):
            await store.append_error(
                thread_id=1,
                error={"step": i, "message": f"Error {i}"},
            )
        errors = await store.get_errors(thread_id=1)
        assert len(errors) == 50
        # Should keep the newest 50 errors (10-59)
        assert errors[0]["step"] == 10
        assert errors[-1]["step"] == 59

    async def test_get_errors_empty(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        errors = await store.get_errors(thread_id=999)
        assert errors == []


class TestSummaryBackup:
    """Tests for summary backup storage (sliding window)."""

    async def test_save_summary_backup(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        now = datetime.now(timezone.utc)
        backup = {
            "summary": {
                "covers_until_turn": 10,
                "user_intent": "Plan Tokyo trip",
            },
            "original_messages": [
                {"role": "user", "content": "I want to go to Tokyo"},
                {"role": "assistant", "content": "Great! When?"},
            ],
            "created_at": now.isoformat(),
        }
        await store.save_summary_backup(thread_id=1, backup=backup)
        backups = await store.get_summary_backups(thread_id=1)
        assert len(backups) == 1
        assert backups[0]["summary"]["user_intent"] == "Plan Tokyo trip"

    async def test_summary_backup_sliding_window_max_20(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(
            redis_client, agent_name="travel", summary_backup_max_count=20
        )
        now = datetime.now(timezone.utc)
        for i in range(25):
            await store.save_summary_backup(
                thread_id=1,
                backup={
                    "summary": {"covers_until_turn": i * 5},
                    "original_messages": [],
                    "created_at": now.isoformat(),
                },
            )
        backups = await store.get_summary_backups(thread_id=1)
        assert len(backups) == 20
        # Should keep newest 20 (5-24)
        assert backups[0]["summary"]["covers_until_turn"] == 25
        assert backups[-1]["summary"]["covers_until_turn"] == 120

    async def test_get_summary_backups_empty(self, redis_client):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore(redis_client, agent_name="travel")
        backups = await store.get_summary_backups(thread_id=999)
        assert backups == []


class TestSessionStateStoreFromUrl:
    """Tests for SessionStateStore.from_url factory method."""

    def test_from_url_creates_store(self):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore.from_url(
            "redis://localhost:6379", agent_name="travel"
        )
        assert isinstance(store, SessionStateStore)
        assert store._agent_name == "travel"

    def test_from_url_custom_options(self):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore.from_url(
            "redis://localhost:6379",
            agent_name="dining",
            ttl_seconds=3600,
            error_max_count=100,
            summary_backup_max_count=50,
        )
        assert store._agent_name == "dining"
        assert store._ttl_seconds == 3600
        assert store._error_max_count == 100
        assert store._summary_backup_max_count == 50

    def test_from_url_rediss_enables_ssl(self):
        from karpo_context.store.session_store import SessionStateStore

        store = SessionStateStore.from_url(
            "rediss://master.my-cache.xxx.use1.cache.amazonaws.com:6379",
            agent_name="travel",
        )
        conn_kwargs = store._redis.connection_pool.connection_kwargs
        assert conn_kwargs.get("ssl") is True
