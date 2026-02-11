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

    def test_create_context_store_importable(self):
        from karpo_context import create_context_store
        assert create_context_store is not None

    def test_context_redis_url_importable(self):
        from karpo_context import CONTEXT_REDIS_URL
        assert CONTEXT_REDIS_URL is not None

    def test_session_state_importable(self):
        from karpo_context import SessionState
        assert SessionState is not None

    def test_conversation_summary_importable(self):
        from karpo_context import ConversationSummary
        assert ConversationSummary is not None

    def test_session_state_store_importable(self):
        from karpo_context import SessionStateStore
        assert SessionStateStore is not None

    def test_context_budget_importable(self):
        from karpo_context import ContextBudget
        assert ContextBudget is not None

    def test_token_budget_manager_importable(self):
        from karpo_context import TokenBudgetManager
        assert TokenBudgetManager is not None

    def test_context_config_importable(self):
        from karpo_context import ContextConfig
        assert ContextConfig is not None

    def test_context_configs_importable(self):
        from karpo_context import CONTEXT_CONFIGS
        assert CONTEXT_CONFIGS is not None

    def test_get_config_importable(self):
        from karpo_context import get_config
        assert get_config is not None

    def test_context_pipeline_importable(self):
        from karpo_context import ContextPipeline
        assert ContextPipeline is not None

    def test_all_contains_all_names(self):
        expected = {
            "ChatMessage",
            "ToolCallRecord",
            "ConversationContext",
            "ConversationSummary",
            "SessionState",
            "ContextBudget",
            "TokenBudgetManager",
            "ContextConfig",
            "CONTEXT_CONFIGS",
            "get_config",
            "ContextStore",
            "RedisContextStore",
            "SessionStateStore",
            "CompactionTrigger",
            "Summarizer",
            "MessageCountTrigger",
            "LLMSummarizer",
            "ContextManager",
            "ContextPipeline",
            "CONTEXT_REDIS_URL",
            "create_context_store",
        }
        assert set(karpo_context.__all__) == expected

    def test_all_has_exactly_21_names(self):
        assert len(karpo_context.__all__) == 21
