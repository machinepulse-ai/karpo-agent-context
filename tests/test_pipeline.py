"""Tests for ContextPipeline - the main entry point for context assembly."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis

from karpo_context.models import SessionState, ConversationSummary
from karpo_context.config import ContextConfig, get_config
from karpo_context.budget import ContextBudget


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def mock_summarizer():
    """Mock summarizer that returns a simple summary."""
    summarizer = AsyncMock()
    summarizer.summarize.return_value = ConversationSummary(
        covers_until_turn=5,
        generated_at=datetime.now(timezone.utc),
        user_intent="Test intent",
        key_entities={},
        decisions_made=[],
        pending_questions=[],
    )
    return summarizer


class TestContextPipelineInit:
    """Tests for ContextPipeline initialization."""

    def test_create_pipeline_with_defaults(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        pipeline = ContextPipeline(
            redis_client=redis_client,
            agent_name="travel",
        )
        assert pipeline is not None
        assert pipeline._agent_name == "travel"

    def test_create_pipeline_with_custom_config(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        config = get_config("fast")
        pipeline = ContextPipeline(
            redis_client=redis_client,
            agent_name="travel",
            config=config,
        )
        assert pipeline._config.budget.total_limit == 4000


class TestContextPipelineLoad:
    """Tests for the Load stage of the pipeline."""

    async def test_load_creates_new_session_if_not_exists(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        pipeline = ContextPipeline(redis_client=redis_client, agent_name="travel")
        session = await pipeline.load(thread_id=1, user_id="user-001")

        assert session is not None
        assert session.thread_id == 1
        assert session.user_id == "user-001"
        assert session.turn_count == 0

    async def test_load_returns_existing_session(self, redis_client):
        from karpo_context.pipeline import ContextPipeline
        from karpo_context.store.session_store import SessionStateStore

        # Pre-create a session
        store = SessionStateStore(redis_client, agent_name="travel")
        now = datetime.now(timezone.utc)
        existing = SessionState(
            thread_id=1,
            user_id="user-001",
            created_at=now,
            updated_at=now,
            turn_count=5,
        )
        existing.add_message("user", "Hello")
        await store.save(existing)

        # Load via pipeline
        pipeline = ContextPipeline(redis_client=redis_client, agent_name="travel")
        session = await pipeline.load(thread_id=1, user_id="user-001")

        assert session.turn_count == 6  # 5 + 1 from add_message
        assert len(session.messages) == 1


class TestContextPipelineMerge:
    """Tests for the Merge stage of the pipeline."""

    async def test_merge_adds_user_message(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        pipeline = ContextPipeline(redis_client=redis_client, agent_name="travel")
        session = await pipeline.load(thread_id=1, user_id="user-001")

        updated = pipeline.merge(session, user_input="I want to go to Tokyo")

        assert len(updated.messages) == 1
        assert updated.messages[0].content == "I want to go to Tokyo"
        assert updated.messages[0].role == "user"
        assert updated.turn_count == 1


class TestContextPipelineEstimate:
    """Tests for the Estimate stage of the pipeline."""

    async def test_estimate_returns_token_counts(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        pipeline = ContextPipeline(redis_client=redis_client, agent_name="travel")
        session = await pipeline.load(thread_id=1, user_id="user-001")
        session = pipeline.merge(session, user_input="I want to go to Tokyo")

        estimate = pipeline.estimate(session, persona="You are a travel agent.")

        assert "total_tokens" in estimate
        assert "persona_tokens" in estimate
        assert "history_tokens" in estimate
        assert "degradation_level" in estimate
        assert estimate["degradation_level"] in [0, 1, 2, 3]

    async def test_estimate_calculates_degradation_level(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        # Use small budget to trigger degradation
        config = ContextConfig(budget=ContextBudget(total_limit=100))
        pipeline = ContextPipeline(
            redis_client=redis_client,
            agent_name="travel",
            config=config,
        )
        session = await pipeline.load(thread_id=1, user_id="user-001")
        # Add many messages to exceed budget
        for i in range(10):
            session = pipeline.merge(session, user_input="A" * 100)

        estimate = pipeline.estimate(session, persona="You are a travel agent.")

        # Should have high degradation level due to small budget
        assert estimate["degradation_level"] >= 2


class TestContextPipelineCompress:
    """Tests for the Compress stage of the pipeline."""

    async def test_compress_trims_history_when_over_budget(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        config = ContextConfig(
            budget=ContextBudget(total_limit=500, recent_history=200)
        )
        pipeline = ContextPipeline(
            redis_client=redis_client,
            agent_name="travel",
            config=config,
        )
        session = await pipeline.load(thread_id=1, user_id="user-001")

        # Add many messages
        for i in range(20):
            session = pipeline.merge(session, user_input=f"Message {i} " * 10)

        original_count = len(session.messages)
        compressed = pipeline.compress(session, persona="Agent")

        # History should be trimmed
        assert len(compressed.messages) <= original_count

    async def test_compress_triggers_summary_when_needed(
        self, redis_client, mock_summarizer
    ):
        from karpo_context.pipeline import ContextPipeline

        config = ContextConfig(summary_trigger_threshold=5)
        pipeline = ContextPipeline(
            redis_client=redis_client,
            agent_name="travel",
            config=config,
            summarizer=mock_summarizer,
        )
        session = await pipeline.load(thread_id=1, user_id="user-001")

        # Add enough messages to trigger summary
        for i in range(6):
            session = pipeline.merge(session, user_input=f"Message {i}")

        compressed = await pipeline.compress_async(session, persona="Agent")

        # Summary should have been generated
        mock_summarizer.summarize.assert_called_once()


class TestContextPipelineAssemble:
    """Tests for the Assemble stage of the pipeline."""

    async def test_assemble_builds_prompt_components(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        pipeline = ContextPipeline(redis_client=redis_client, agent_name="travel")
        session = await pipeline.load(thread_id=1, user_id="user-001")
        session = pipeline.merge(session, user_input="I want to go to Tokyo")

        result = pipeline.assemble(
            session,
            persona="You are a travel agent.",
            instruction="Help plan trips.",
        )

        assert "system_prompt" in result
        assert "messages" in result
        assert result["messages"][-1]["content"] == "I want to go to Tokyo"

    async def test_assemble_includes_summary_when_present(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        pipeline = ContextPipeline(redis_client=redis_client, agent_name="travel")
        session = await pipeline.load(thread_id=1, user_id="user-001")
        session.summary = ConversationSummary(
            covers_until_turn=5,
            generated_at=datetime.now(timezone.utc),
            user_intent="Plan Tokyo trip",
            key_entities={"destination": "Tokyo"},
            decisions_made=["March departure"],
            pending_questions=[],
        )
        session = pipeline.merge(session, user_input="What about hotels?")

        result = pipeline.assemble(
            session,
            persona="You are a travel agent.",
            instruction="Help plan trips.",
        )

        # Summary should be included in system prompt
        assert "Tokyo" in result["system_prompt"]
        assert "Plan Tokyo trip" in result["system_prompt"]


class TestContextPipelineComplete:
    """Tests for the Complete stage of the pipeline."""

    async def test_complete_saves_session(self, redis_client):
        from karpo_context.pipeline import ContextPipeline
        from karpo_context.store.session_store import SessionStateStore

        pipeline = ContextPipeline(redis_client=redis_client, agent_name="travel")
        session = await pipeline.load(thread_id=1, user_id="user-001")
        session = pipeline.merge(session, user_input="Hello")

        await pipeline.complete(session, assistant_response="Hi there!")

        # Verify saved
        store = SessionStateStore(redis_client, agent_name="travel")
        loaded = await store.get(1)
        assert len(loaded.messages) == 2
        assert loaded.messages[1].content == "Hi there!"
        assert loaded.messages[1].role == "assistant"

    async def test_complete_adds_assistant_message(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        pipeline = ContextPipeline(redis_client=redis_client, agent_name="travel")
        session = await pipeline.load(thread_id=1, user_id="user-001")
        session = pipeline.merge(session, user_input="Hello")

        updated = await pipeline.complete(session, assistant_response="Hi!")

        assert len(updated.messages) == 2
        assert updated.messages[1].role == "assistant"
        assert updated.messages[1].content == "Hi!"


class TestContextPipelineFullCycle:
    """Tests for full pipeline cycle."""

    async def test_full_conversation_cycle(self, redis_client):
        from karpo_context.pipeline import ContextPipeline

        pipeline = ContextPipeline(redis_client=redis_client, agent_name="travel")

        # Turn 1
        session = await pipeline.load(thread_id=1, user_id="user-001")
        session = pipeline.merge(session, user_input="I want to go to Tokyo")
        estimate = pipeline.estimate(session, persona="Travel agent")
        session = pipeline.compress(session, persona="Travel agent")
        result = pipeline.assemble(session, persona="Travel agent")
        session = await pipeline.complete(session, assistant_response="When?")

        assert session.turn_count == 1
        assert len(session.messages) == 2

        # Turn 2
        session = await pipeline.load(thread_id=1, user_id="user-001")
        session = pipeline.merge(session, user_input="March 2026")
        result = pipeline.assemble(session, persona="Travel agent")
        session = await pipeline.complete(session, assistant_response="Great!")

        assert session.turn_count == 2
        assert len(session.messages) == 4
