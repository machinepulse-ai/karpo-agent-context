"""Abstract base class for context storage."""
from abc import ABC, abstractmethod

from karpo_context.models import ConversationContext


class ContextStore(ABC):
    """Abstract interface for persisting conversation context."""

    @abstractmethod
    async def get(self, conversation_id: int) -> ConversationContext | None:
        """Load a conversation context by ID. Returns None if not found."""

    @abstractmethod
    async def save(self, context: ConversationContext) -> None:
        """Persist a conversation context."""

    @abstractmethod
    async def delete(self, conversation_id: int) -> None:
        """Delete a conversation context by ID. No-op if not found."""
