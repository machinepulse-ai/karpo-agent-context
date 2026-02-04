"""ContextManager — unified entry point for managing conversation context."""
from datetime import datetime, timezone

from karpo_context.compaction.base import CompactionTrigger, Summarizer
from karpo_context.models import ChatMessage, ConversationContext
from karpo_context.store.base import ContextStore


class ContextManager:
    """Orchestrates context loading, saving, and auto-compaction."""

    def __init__(
        self,
        store: ContextStore,
        trigger: CompactionTrigger | None = None,
        summarizer: Summarizer | None = None,
        keep_recent: int = 10,
    ) -> None:
        self._store = store
        self._trigger = trigger
        self._summarizer = summarizer
        self._keep_recent = keep_recent

    async def load(self, conversation_id: int) -> ConversationContext:
        """Load a conversation context, creating a new one if it doesn't exist."""
        ctx = await self._store.get(conversation_id)
        if ctx is not None:
            return ctx
        now = datetime.now(timezone.utc)
        return ConversationContext(
            conversation_id=conversation_id,
            created_at=now,
            updated_at=now,
        )

    async def save(self, context: ConversationContext) -> None:
        """Save a conversation context, compacting if the trigger fires."""
        if (
            self._trigger is not None
            and self._summarizer is not None
            and self._trigger.should_compact(context)
        ):
            await self._compact(context)
        await self._store.save(context)

    async def append_message(
        self, conversation_id: int, message: ChatMessage
    ) -> ConversationContext:
        """Append a message to a conversation, saving afterward."""
        ctx = await self.load(conversation_id)
        ctx.messages.append(message)
        ctx.message_count += 1
        now = datetime.now(timezone.utc)
        ctx.updated_at = now
        await self.save(ctx)
        return ctx

    async def _compact(self, context: ConversationContext) -> None:
        """Summarize older messages, keeping only the most recent ones."""
        to_compress = context.messages[: -self._keep_recent]
        to_keep = context.messages[-self._keep_recent :]
        summary = await self._summarizer.summarize(to_compress, context.summary)
        context.summary = summary
        context.messages = to_keep
        context.message_count = len(to_keep)
