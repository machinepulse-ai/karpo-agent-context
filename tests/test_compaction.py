"""Tests for karpo_context.compaction layer."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest


class TestCompactionTriggerABC:
    def test_cannot_instantiate(self):
        from karpo_context.compaction.base import CompactionTrigger

        with pytest.raises(TypeError):
            CompactionTrigger()

    def test_has_should_compact_method(self):
        from karpo_context.compaction.base import CompactionTrigger

        assert hasattr(CompactionTrigger, "should_compact")


class TestSummarizerABC:
    def test_cannot_instantiate(self):
        from karpo_context.compaction.base import Summarizer

        with pytest.raises(TypeError):
            Summarizer()

    def test_has_summarize_method(self):
        from karpo_context.compaction.base import Summarizer

        assert hasattr(Summarizer, "summarize")


class TestMessageCountTrigger:
    def test_is_subclass(self):
        from karpo_context.compaction.base import CompactionTrigger
        from karpo_context.compaction.message_count import MessageCountTrigger

        assert issubclass(MessageCountTrigger, CompactionTrigger)

    def test_no_compact_below_threshold(self):
        from karpo_context.compaction.message_count import MessageCountTrigger
        from karpo_context.models import ChatMessage, ConversationContext

        now = datetime.now(timezone.utc)
        trigger = MessageCountTrigger(threshold=5)
        ctx = ConversationContext(
            conversation_id=1,
            messages=[
                ChatMessage(role="user", content=f"msg{i}", created_at=now)
                for i in range(3)
            ],
            created_at=now,
            updated_at=now,
        )
        assert trigger.should_compact(ctx) is False

    def test_compact_above_threshold(self):
        from karpo_context.compaction.message_count import MessageCountTrigger
        from karpo_context.models import ChatMessage, ConversationContext

        now = datetime.now(timezone.utc)
        trigger = MessageCountTrigger(threshold=5)
        ctx = ConversationContext(
            conversation_id=1,
            messages=[
                ChatMessage(role="user", content=f"msg{i}", created_at=now)
                for i in range(8)
            ],
            created_at=now,
            updated_at=now,
        )
        assert trigger.should_compact(ctx) is True

    def test_not_at_exactly_threshold(self):
        from karpo_context.compaction.message_count import MessageCountTrigger
        from karpo_context.models import ChatMessage, ConversationContext

        now = datetime.now(timezone.utc)
        trigger = MessageCountTrigger(threshold=5)
        ctx = ConversationContext(
            conversation_id=1,
            messages=[
                ChatMessage(role="user", content=f"msg{i}", created_at=now)
                for i in range(5)
            ],
            created_at=now,
            updated_at=now,
        )
        assert trigger.should_compact(ctx) is False

    def test_default_threshold_is_50(self):
        from karpo_context.compaction.message_count import MessageCountTrigger

        trigger = MessageCountTrigger()
        assert trigger._threshold == 50


class TestLLMSummarizer:
    def test_is_subclass(self):
        from karpo_context.compaction.base import Summarizer
        from karpo_context.compaction.summarizer import LLMSummarizer

        assert issubclass(LLMSummarizer, Summarizer)

    async def test_summarize_without_existing_summary(self):
        from karpo_context.compaction.summarizer import LLMSummarizer
        from karpo_context.models import ChatMessage

        now = datetime.now(timezone.utc)
        llm = AsyncMock(return_value="Summary of the conversation.")
        summarizer = LLMSummarizer(llm_callable=llm)

        messages = [
            ChatMessage(role="user", content="Hello", created_at=now),
            ChatMessage(role="assistant", content="Hi there!", created_at=now),
        ]
        result = await summarizer.summarize(messages)
        assert result == "Summary of the conversation."
        llm.assert_awaited_once()
        # Verify the prompt does NOT contain existing summary section
        prompt = llm.call_args[0][0]
        assert "Previous summary" not in prompt

    async def test_summarize_with_existing_summary(self):
        from karpo_context.compaction.summarizer import LLMSummarizer
        from karpo_context.models import ChatMessage

        now = datetime.now(timezone.utc)
        llm = AsyncMock(return_value="Updated summary.")
        summarizer = LLMSummarizer(llm_callable=llm)

        messages = [
            ChatMessage(role="user", content="What's new?", created_at=now),
        ]
        result = await summarizer.summarize(messages, existing_summary="Old summary.")
        assert result == "Updated summary."
        prompt = llm.call_args[0][0]
        assert "Old summary." in prompt

    async def test_custom_prompt_template(self):
        from karpo_context.compaction.summarizer import LLMSummarizer
        from karpo_context.models import ChatMessage

        now = datetime.now(timezone.utc)
        llm = AsyncMock(return_value="Custom summary.")
        template = "Custom template. Messages:\n{messages}"
        summarizer = LLMSummarizer(llm_callable=llm, prompt_template=template)

        messages = [
            ChatMessage(role="user", content="Test", created_at=now),
        ]
        result = await summarizer.summarize(messages)
        assert result == "Custom summary."
        prompt = llm.call_args[0][0]
        assert "Custom template." in prompt
