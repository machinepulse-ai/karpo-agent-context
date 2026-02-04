"""Abstract base classes for compaction."""
from abc import ABC, abstractmethod

from karpo_context.models import ChatMessage, ConversationContext


class CompactionTrigger(ABC):
    """Determines when conversation context should be compacted."""

    @abstractmethod
    def should_compact(self, context: ConversationContext) -> bool:
        """Return True if the context should be compacted."""


class Summarizer(ABC):
    """Summarizes a list of messages into a text summary."""

    @abstractmethod
    async def summarize(
        self,
        messages: list[ChatMessage],
        existing_summary: str | None = None,
    ) -> str:
        """Produce a summary of the given messages, optionally incorporating an existing summary."""
