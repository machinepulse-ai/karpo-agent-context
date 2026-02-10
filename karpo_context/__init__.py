"""karpo-context: Shared package for managing agent conversation context."""
from karpo_context.budget import ContextBudget, TokenBudgetManager
from karpo_context.compaction.base import CompactionTrigger, Summarizer
from karpo_context.compaction.message_count import MessageCountTrigger
from karpo_context.compaction.summarizer import LLMSummarizer
from karpo_context.config import CONTEXT_CONFIGS, ContextConfig, get_config
from karpo_context.defaults import CONTEXT_REDIS_URL, create_context_store
from karpo_context.manager import ContextManager
from karpo_context.models import (
    ChatMessage,
    ConversationContext,
    ConversationSummary,
    SessionState,
    ToolCallRecord,
)
from karpo_context.store.base import ContextStore
from karpo_context.store.redis_store import RedisContextStore
from karpo_context.store.session_store import SessionStateStore

__all__ = [
    # Models
    "ChatMessage",
    "ToolCallRecord",
    "ConversationContext",
    "ConversationSummary",
    "SessionState",
    # Budget management
    "ContextBudget",
    "TokenBudgetManager",
    # Configuration
    "ContextConfig",
    "CONTEXT_CONFIGS",
    "get_config",
    # Storage
    "ContextStore",
    "RedisContextStore",
    "SessionStateStore",
    # Compaction
    "CompactionTrigger",
    "Summarizer",
    "MessageCountTrigger",
    "LLMSummarizer",
    # Manager
    "ContextManager",
    # Defaults
    "CONTEXT_REDIS_URL",
    "create_context_store",
]
