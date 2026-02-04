"""Tests for karpo_context public API exports."""
import karpo_context


class TestPublicExports:
    def test_chat_message_importable(self):
        from karpo_context import ChatMessage
        assert ChatMessage is not None

    def test_tool_call_record_importable(self):
        from karpo_context import ToolCallRecord
        assert ToolCallRecord is not None

    def test_conversation_context_importable(self):
        from karpo_context import ConversationContext
        assert ConversationContext is not None

    def test_context_store_importable(self):
        from karpo_context import ContextStore
        assert ContextStore is not None

    def test_redis_context_store_importable(self):
        from karpo_context import RedisContextStore
        assert RedisContextStore is not None

    def test_compaction_trigger_importable(self):
        from karpo_context import CompactionTrigger
        assert CompactionTrigger is not None

    def test_summarizer_importable(self):
        from karpo_context import Summarizer
        assert Summarizer is not None

    def test_message_count_trigger_importable(self):
        from karpo_context import MessageCountTrigger
        assert MessageCountTrigger is not None

    def test_llm_summarizer_importable(self):
        from karpo_context import LLMSummarizer
        assert LLMSummarizer is not None

    def test_context_manager_importable(self):
        from karpo_context import ContextManager
        assert ContextManager is not None

    def test_all_contains_all_names(self):
        expected = {
            "ChatMessage",
            "ToolCallRecord",
            "ConversationContext",
            "ContextStore",
            "RedisContextStore",
            "CompactionTrigger",
            "Summarizer",
            "MessageCountTrigger",
            "LLMSummarizer",
            "ContextManager",
        }
        assert set(karpo_context.__all__) == expected

    def test_all_has_exactly_10_names(self):
        assert len(karpo_context.__all__) == 10
