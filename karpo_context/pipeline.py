"""Context pipeline for assembling conversation context."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from redis.asyncio import Redis

from karpo_context.budget import TokenBudgetManager
from karpo_context.config import ContextConfig, get_config
from karpo_context.models import ConversationSummary, SessionState
from karpo_context.store.session_store import SessionStateStore


class Summarizer(Protocol):
    """Protocol for summarizer implementations."""

    async def summarize(
        self,
        messages: list[dict[str, Any]],
        existing_summary: str | None = None,
    ) -> ConversationSummary:
        """Generate a summary from messages."""
        ...


class ContextPipeline:
    """Main entry point for context management.

    Implements a 6-stage pipeline:
    1. Load: Get or create session from Redis
    2. Merge: Add new user message
    3. Estimate: Calculate token usage
    4. Compress: Apply compression if needed
    5. Assemble: Build prompt components
    6. Complete: Save session with assistant response
    """

    def __init__(
        self,
        redis_client: Redis,
        agent_name: str,
        config: ContextConfig | None = None,
        summarizer: Summarizer | None = None,
    ) -> None:
        self._agent_name = agent_name
        self._config = config or get_config(None)
        self._store = SessionStateStore(
            redis_client,
            agent_name=agent_name,
            ttl_seconds=7 * 24 * 3600,
            error_max_count=self._config.error_max_count,
            summary_backup_max_count=self._config.summary_backup_max_count,
        )
        self._budget_manager = TokenBudgetManager(self._config.budget)
        self._summarizer = summarizer

    async def load(self, thread_id: int, user_id: str) -> SessionState:
        """Load or create a session.

        Stage 1: Load session from Redis or create new one.
        """
        session = await self._store.get(thread_id)
        if session is None:
            now = datetime.now(timezone.utc)
            session = SessionState(
                thread_id=thread_id,
                user_id=user_id,
                created_at=now,
                updated_at=now,
            )
        return session

    def merge(self, session: SessionState, user_input: str) -> SessionState:
        """Add user message to session.

        Stage 2: Merge new user input into session.
        """
        session.add_message("user", user_input)
        return session

    def estimate(
        self,
        session: SessionState,
        persona: str,
        instruction: str = "",
        emotional_context: str = "",
    ) -> dict[str, Any]:
        """Estimate token usage for current session.

        Stage 3: Calculate token counts and degradation level.
        """
        # Estimate each component
        persona_tokens = self._budget_manager.estimate_tokens(persona)
        instruction_tokens = self._budget_manager.estimate_tokens(instruction)
        emotional_tokens = self._budget_manager.estimate_tokens(emotional_context)

        # Estimate summary tokens
        summary_tokens = 0
        if session.summary:
            summary_text = self._format_summary(session.summary)
            summary_tokens = self._budget_manager.estimate_tokens(summary_text)

        # Estimate history tokens
        history_messages = [
            {"role": m.role, "content": m.content or ""}
            for m in session.messages
        ]
        history_tokens = self._budget_manager.estimate_messages_tokens(history_messages)

        # Calculate total and degradation
        total_tokens = (
            persona_tokens
            + instruction_tokens
            + emotional_tokens
            + summary_tokens
            + history_tokens
        )
        degradation_level = self._budget_manager.calculate_degradation_level(total_tokens)

        return {
            "persona_tokens": persona_tokens,
            "instruction_tokens": instruction_tokens,
            "emotional_tokens": emotional_tokens,
            "summary_tokens": summary_tokens,
            "history_tokens": history_tokens,
            "total_tokens": total_tokens,
            "degradation_level": degradation_level,
            "should_trigger_summary": self._budget_manager.should_trigger_summary(
                total_tokens,
                session.turn_count,
                self._config.summary_trigger_threshold,
            ),
        }

    def compress(
        self,
        session: SessionState,
        persona: str,
        instruction: str = "",
    ) -> SessionState:
        """Apply compression to fit within budget.

        Stage 4: Trim history or trigger summary if needed.
        Synchronous version - only trims history.
        """
        # Calculate available budget for history
        persona_tokens = self._budget_manager.estimate_tokens(persona)
        instruction_tokens = self._budget_manager.estimate_tokens(instruction)

        summary_tokens = 0
        if session.summary:
            summary_text = self._format_summary(session.summary)
            summary_tokens = self._budget_manager.estimate_tokens(summary_text)

        remaining = self._budget_manager.get_remaining_for_history(
            persona_tokens=persona_tokens,
            instruction_tokens=instruction_tokens,
            summary_tokens=summary_tokens,
        )

        # Trim history from oldest if needed
        messages = list(session.messages)
        while messages:
            history_messages = [
                {"role": m.role, "content": m.content or ""}
                for m in messages
            ]
            history_tokens = self._budget_manager.estimate_messages_tokens(history_messages)
            if history_tokens <= remaining:
                break
            # Remove oldest message
            messages.pop(0)

        session.messages = messages
        return session

    async def compress_async(
        self,
        session: SessionState,
        persona: str,
        instruction: str = "",
    ) -> SessionState:
        """Apply compression asynchronously, including summary generation.

        Stage 4 (async): May generate summary if needed.
        """
        estimate = self.estimate(session, persona, instruction)

        # Check if summary should be triggered
        if (
            estimate["should_trigger_summary"]
            and self._summarizer is not None
            and len(session.messages) > 0
        ):
            # Generate summary from messages
            history_messages = [
                {"role": m.role, "content": m.content or ""}
                for m in session.messages
            ]
            existing_summary = None
            if session.summary:
                existing_summary = self._format_summary(session.summary)

            summary = await self._summarizer.summarize(
                history_messages, existing_summary
            )
            session.summary = summary

        # Apply sync compression (history trimming)
        return self.compress(session, persona, instruction)

    def assemble(
        self,
        session: SessionState,
        persona: str,
        instruction: str = "",
        emotional_context: str = "",
    ) -> dict[str, Any]:
        """Assemble prompt components for LLM call.

        Stage 5: Build system prompt and messages list.
        """
        # Build system prompt
        system_parts = [persona]

        if instruction:
            system_parts.append(f"\n\n{instruction}")

        if session.summary:
            summary_text = self._format_summary(session.summary)
            system_parts.append(f"\n\n## Conversation Summary\n{summary_text}")

        if emotional_context and self._config.enable_emotional_context:
            system_parts.append(f"\n\n## Context\n{emotional_context}")

        system_prompt = "".join(system_parts)

        # Build messages list
        messages = [
            {"role": m.role, "content": m.content}
            for m in session.messages
            if m.content is not None
        ]

        return {
            "system_prompt": system_prompt,
            "messages": messages,
        }

    async def complete(
        self,
        session: SessionState,
        assistant_response: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> SessionState:
        """Save session with assistant response.

        Stage 6: Add assistant message and persist to Redis.
        """
        session.add_message("assistant", assistant_response, tool_calls=tool_calls)
        await self._store.save(session)
        return session

    def _format_summary(self, summary: ConversationSummary) -> str:
        """Format summary for inclusion in prompt."""
        parts = [f"User intent: {summary.user_intent}"]

        if summary.key_entities:
            entities = ", ".join(f"{k}: {v}" for k, v in summary.key_entities.items())
            parts.append(f"Key information: {entities}")

        if summary.decisions_made:
            decisions = ", ".join(summary.decisions_made)
            parts.append(f"Decisions: {decisions}")

        if summary.pending_questions:
            questions = ", ".join(summary.pending_questions)
            parts.append(f"Pending: {questions}")

        return "\n".join(parts)
