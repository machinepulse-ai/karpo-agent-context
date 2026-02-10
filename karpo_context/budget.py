"""Token budget management for context assembly."""

from dataclasses import dataclass


@dataclass
class ContextBudget:
    """Token budget configuration for context components.

    Default values are tuned for 8K context window models.
    """

    total_limit: int = 8000
    persona_prompt: int = 1000
    response_instruction: int = 500
    conversation_summary: int = 500
    emotional_context: int = 100
    recent_history: int = 4000
    current_input: int = 500
    output_buffer: int = 1400


class TokenBudgetManager:
    """Manages token budget allocation and estimation.

    Provides:
    - Token estimation for text and messages
    - Budget checking for each component
    - Degradation level calculation
    - Summary trigger decision
    """

    # Rough estimation: 1 token ≈ 4 chars (English), ≈ 1.5 chars (Chinese)
    CHARS_PER_TOKEN_EN = 4
    CHARS_PER_TOKEN_ZH = 1.5

    def __init__(self, budget: ContextBudget | None = None) -> None:
        """Initialize with optional budget configuration."""
        self.budget = budget or ContextBudget()

    def get_budget(self) -> ContextBudget:
        """Get current budget configuration."""
        return self.budget

    def estimate_tokens(self, text: str | None) -> int:
        """Estimate token count for given text.

        Uses a simple heuristic based on character count and
        Chinese/English ratio.
        """
        if not text:
            return 0

        # Count Chinese characters
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        total_chars = len(text)

        if total_chars == 0:
            return 0

        chinese_ratio = chinese_chars / total_chars

        # Weighted average based on language mix
        avg_chars_per_token = (
            self.CHARS_PER_TOKEN_ZH * chinese_ratio
            + self.CHARS_PER_TOKEN_EN * (1 - chinese_ratio)
        )

        return int(total_chars / avg_chars_per_token)

    def estimate_messages_tokens(self, messages: list[dict]) -> int:
        """Estimate total tokens for a list of messages."""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            # Add overhead for role and formatting (~4 tokens per message)
            total += self.estimate_tokens(content) + 4
        return total

    def check_budget(
        self,
        persona_tokens: int,
        instruction_tokens: int,
        emotional_tokens: int,
        summary_tokens: int,
        history_tokens: int,
        input_tokens: int,
    ) -> dict[str, bool | int]:
        """Check if each component is within budget.

        Returns:
            Dict with component names and whether they're within budget,
            plus total_used and total_available as ints.
        """
        total_used = (
            persona_tokens
            + instruction_tokens
            + emotional_tokens
            + summary_tokens
            + history_tokens
            + input_tokens
        )

        return {
            "persona": persona_tokens <= self.budget.persona_prompt,
            "instruction": instruction_tokens <= self.budget.response_instruction,
            "emotional": emotional_tokens <= self.budget.emotional_context,
            "summary": summary_tokens <= self.budget.conversation_summary,
            "history": history_tokens <= self.budget.recent_history,
            "input": input_tokens <= self.budget.current_input,
            "total": total_used <= (self.budget.total_limit - self.budget.output_buffer),
            "total_used": total_used,
            "total_available": self.budget.total_limit - self.budget.output_buffer,
        }

    def get_remaining_for_history(
        self,
        persona_tokens: int,
        instruction_tokens: int,
        emotional_tokens: int = 0,
        summary_tokens: int = 0,
        input_tokens: int = 0,
    ) -> int:
        """Calculate remaining budget available for history.

        This helps determine how many history messages can be included
        after allocating budget for other components.
        """
        used = (
            persona_tokens
            + instruction_tokens
            + emotional_tokens
            + summary_tokens
            + input_tokens
            + self.budget.output_buffer
        )
        remaining = self.budget.total_limit - used
        # Cap at history budget
        return min(max(0, remaining), self.budget.recent_history)

    def calculate_degradation_level(self, total_tokens: int) -> int:
        """Calculate degradation level based on token usage.

        Returns:
            0: Normal - full context
            1: Light pressure - reduce history by 30%
            2: Medium pressure - compress + trim emotional
            3: Heavy pressure - summary only + last 3 turns
        """
        available = self.budget.total_limit - self.budget.output_buffer

        if total_tokens <= available * 0.7:
            return 0  # Normal
        elif total_tokens <= available * 0.85:
            return 1  # Light pressure
        elif total_tokens <= available:
            return 2  # Medium pressure
        else:
            return 3  # Heavy pressure

    def predict_next_turn_ratio(self, current_tokens: int) -> float:
        """Predict token usage ratio for next turn.

        Returns ratio of current tokens to available budget.
        """
        available = self.budget.total_limit - self.budget.output_buffer
        return current_tokens / available if available > 0 else 1.0

    def should_trigger_summary(
        self,
        current_tokens: int,
        turn_count: int,
        threshold: int,
    ) -> bool:
        """Determine if summary should be triggered.

        Triggers when:
        - Token usage > 70% of available budget, OR
        - Turn count >= threshold
        """
        ratio = self.predict_next_turn_ratio(current_tokens)
        return ratio > 0.7 or turn_count >= threshold
