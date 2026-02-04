"""karpo-context: Shared package for managing agent conversation context."""
from karpo_context.compaction.base import CompactionTrigger, Summarizer
from karpo_context.compaction.message_count import MessageCountTrigger
from karpo_context.compaction.summarizer import LLMSummarizer
from karpo_context.manager import ContextManager
from karpo_context.models import ChatMessage, ConversationContext, ToolCallRecord
from karpo_context.store.base import ContextStore
from karpo_context.store.redis_store import RedisContextStore

__all__ = [
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
]
