"""Tests for TokenBudgetManager."""

import pytest

from karpo_context.budget import TokenBudgetManager, ContextBudget


class TestContextBudget:
    """Tests for ContextBudget configuration."""

    def test_default_budget(self):
        """Test default budget values."""
        budget = ContextBudget()

        assert budget.total_limit == 8000
        assert budget.persona_prompt == 1000
        assert budget.response_instruction == 500
        assert budget.conversation_summary == 500
        assert budget.emotional_context == 100
        assert budget.recent_history == 4000
        assert budget.current_input == 500
        assert budget.output_buffer == 1400

    def test_custom_budget(self):
        """Test custom budget values."""
        budget = ContextBudget(
            total_limit=16000,
            persona_prompt=2000,
            recent_history=8000,
        )

        assert budget.total_limit == 16000
        assert budget.persona_prompt == 2000
        assert budget.recent_history == 8000


class TestTokenBudgetManager:
    """Tests for TokenBudgetManager."""

    def test_init_with_default_budget(self):
        """Test initialization with default budget."""
        manager = TokenBudgetManager()
        budget = manager.get_budget()

        assert budget.total_limit == 8000

    def test_init_with_custom_budget(self):
        """Test initialization with custom budget."""
        custom = ContextBudget(total_limit=16000)
        manager = TokenBudgetManager(budget=custom)

        assert manager.get_budget().total_limit == 16000

    def test_estimate_tokens_empty(self):
        """Test token estimation for empty string."""
        manager = TokenBudgetManager()

        assert manager.estimate_tokens("") == 0
        assert manager.estimate_tokens(None) == 0

    def test_estimate_tokens_english(self):
        """Test token estimation for English text."""
        manager = TokenBudgetManager()

        # ~4 chars per token for English
        text = "Hello world"  # 11 chars
        tokens = manager.estimate_tokens(text)

        # 11 / 4 = 2.75 -> 2
        assert tokens == 2

    def test_estimate_tokens_chinese(self):
        """Test token estimation for Chinese text."""
        manager = TokenBudgetManager()

        # ~1.5 chars per token for Chinese
        text = "你好世界"  # 4 Chinese chars
        tokens = manager.estimate_tokens(text)

        # 4 / 1.5 = 2.67 -> 2
        assert tokens == 2

    def test_estimate_tokens_mixed(self):
        """Test token estimation for mixed language text."""
        manager = TokenBudgetManager()

        # Mixed: "Hello 你好" = 6 English + 2 Chinese = 8 chars total
        # Chinese ratio = 2/8 = 0.25
        # avg_chars_per_token = 1.5 * 0.25 + 4 * 0.75 = 0.375 + 3 = 3.375
        # tokens = 8 / 3.375 = 2.37 -> 2
        text = "Hello 你好"
        tokens = manager.estimate_tokens(text)

        assert tokens == 2

    def test_estimate_messages_tokens(self):
        """Test token estimation for message list."""
        manager = TokenBudgetManager()

        messages = [
            {"role": "user", "content": "Hello"},  # 5 chars -> 1 token + 4 overhead
            {"role": "assistant", "content": "Hi there!"},  # 9 chars -> 2 tokens + 4 overhead
        ]
        tokens = manager.estimate_messages_tokens(messages)

        # (1 + 4) + (2 + 4) = 11
        assert tokens == 11

    def test_estimate_messages_tokens_empty(self):
        """Test token estimation for empty message list."""
        manager = TokenBudgetManager()

        assert manager.estimate_messages_tokens([]) == 0

    def test_check_budget_all_within(self):
        """Test budget check when all components are within limits."""
        manager = TokenBudgetManager()

        result = manager.check_budget(
            persona_tokens=500,
            instruction_tokens=200,
            emotional_tokens=50,
            summary_tokens=200,
            history_tokens=2000,
            input_tokens=200,
        )

        assert result["persona"] is True
        assert result["instruction"] is True
        assert result["emotional"] is True
        assert result["summary"] is True
        assert result["history"] is True
        assert result["input"] is True
        assert result["total"] is True
        assert result["total_used"] == 3150
        assert result["total_available"] == 6600  # 8000 - 1400

    def test_check_budget_exceeding(self):
        """Test budget check when components exceed limits."""
        manager = TokenBudgetManager()

        result = manager.check_budget(
            persona_tokens=1500,  # Exceeds 1000
            instruction_tokens=200,
            emotional_tokens=200,  # Exceeds 100
            summary_tokens=200,
            history_tokens=5000,  # Exceeds 4000
            input_tokens=200,
        )

        assert result["persona"] is False
        assert result["emotional"] is False
        assert result["history"] is False
        assert result["total"] is False  # Total exceeds available

    def test_calculate_degradation_level_normal(self):
        """Test degradation level for normal usage."""
        manager = TokenBudgetManager()

        # 70% of 6600 = 4620
        level = manager.calculate_degradation_level(4000)
        assert level == 0

    def test_calculate_degradation_level_light(self):
        """Test degradation level for light pressure."""
        manager = TokenBudgetManager()

        # Between 70% (4620) and 85% (5610) of 6600
        level = manager.calculate_degradation_level(5000)
        assert level == 1

    def test_calculate_degradation_level_medium(self):
        """Test degradation level for medium pressure."""
        manager = TokenBudgetManager()

        # Between 85% (5610) and 100% (6600) of 6600
        level = manager.calculate_degradation_level(6000)
        assert level == 2

    def test_calculate_degradation_level_heavy(self):
        """Test degradation level for heavy pressure."""
        manager = TokenBudgetManager()

        # Over 100% of 6600
        level = manager.calculate_degradation_level(7000)
        assert level == 3

    def test_get_remaining_for_history(self):
        """Test calculating remaining budget for history."""
        manager = TokenBudgetManager()

        # Used: 500 (persona) + 200 (instruction) + 50 (emotional) + 200 (summary)
        #       + 200 (input) + 1400 (output_buffer) = 2550
        # Remaining: 8000 - 2550 = 5450
        # But capped at history budget (4000)
        remaining = manager.get_remaining_for_history(
            persona_tokens=500,
            instruction_tokens=200,
            emotional_tokens=50,
            summary_tokens=200,
            input_tokens=200,
        )

        assert remaining == 4000

    def test_get_remaining_for_history_limited(self):
        """Test remaining budget when limited by total."""
        manager = TokenBudgetManager()

        # Used: 3000 (persona) + 2000 (instruction) + 500 (emotional) + 500 (summary)
        #       + 500 (input) + 1400 (output_buffer) = 7900
        # Remaining: 8000 - 7900 = 100
        remaining = manager.get_remaining_for_history(
            persona_tokens=3000,
            instruction_tokens=2000,
            emotional_tokens=500,
            summary_tokens=500,
            input_tokens=500,
        )

        assert remaining == 100

    def test_predict_next_turn_ratio(self):
        """Test predicting token ratio for next turn."""
        budget = ContextBudget(total_limit=8000, output_buffer=1400)
        manager = TokenBudgetManager(budget=budget)

        # Current tokens = 4000, available = 6600
        ratio = manager.predict_next_turn_ratio(4000)

        # 4000 / 6600 = 0.606
        assert 0.60 <= ratio <= 0.61

    def test_should_trigger_summary(self):
        """Test summary trigger decision."""
        manager = TokenBudgetManager()

        # Below 70% threshold
        assert manager.should_trigger_summary(4000, turn_count=10, threshold=20) is False

        # Above 70% threshold (4620)
        assert manager.should_trigger_summary(5000, turn_count=10, threshold=20) is True

        # Below token threshold but above turn threshold
        assert manager.should_trigger_summary(4000, turn_count=25, threshold=20) is True
