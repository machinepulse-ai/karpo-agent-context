"""Message-count-based compaction trigger."""
from karpo_context.compaction.base import CompactionTrigger
from karpo_context.models import ConversationContext


class MessageCountTrigger(CompactionTrigger):
    """Triggers compaction when message count exceeds a threshold."""

    def __init__(self, threshold: int = 50) -> None:
        self._threshold = threshold

    def should_compact(self, context: ConversationContext) -> bool:
        return len(context.messages) > self._threshold
