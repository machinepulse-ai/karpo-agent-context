"""Tests for ContextConfig and presets."""
import pytest

from karpo_context.budget import ContextBudget


class TestContextConfig:
    """Tests for ContextConfig dataclass."""

    def test_create_default_config(self):
        from karpo_context.config import ContextConfig

        config = ContextConfig()
        assert config.budget is not None
        assert config.summary_trigger_threshold == 20
        assert config.enable_emotional_context is True
        assert config.enable_proactive_summary is True

    def test_create_custom_config(self):
        from karpo_context.config import ContextConfig

        budget = ContextBudget(total_limit=16000)
        config = ContextConfig(
            budget=budget,
            summary_trigger_threshold=30,
            enable_emotional_context=False,
            enable_proactive_summary=False,
        )
        assert config.budget.total_limit == 16000
        assert config.summary_trigger_threshold == 30
        assert config.enable_emotional_context is False
        assert config.enable_proactive_summary is False

    def test_config_has_sliding_window_settings(self):
        from karpo_context.config import ContextConfig

        config = ContextConfig()
        assert config.error_max_count == 50
        assert config.summary_backup_max_count == 20

    def test_config_has_compression_settings(self):
        from karpo_context.config import ContextConfig

        config = ContextConfig()
        assert config.proactive_summary_threshold == 0.7
        assert config.tool_result_offload_threshold == 500


class TestContextConfigPresets:
    """Tests for predefined context config presets."""

    def test_fast_preset_exists(self):
        from karpo_context.config import CONTEXT_CONFIGS

        assert "fast" in CONTEXT_CONFIGS

    def test_personalized_preset_exists(self):
        from karpo_context.config import CONTEXT_CONFIGS

        assert "personalized" in CONTEXT_CONFIGS

    def test_planning_preset_exists(self):
        from karpo_context.config import CONTEXT_CONFIGS

        assert "planning" in CONTEXT_CONFIGS

    def test_fast_preset_has_small_budget(self):
        from karpo_context.config import CONTEXT_CONFIGS

        fast = CONTEXT_CONFIGS["fast"]
        # Fast mode should have smaller budget for quick responses
        assert fast.budget.total_limit == 4000
        assert fast.enable_emotional_context is False
        assert fast.summary_trigger_threshold == 10

    def test_personalized_preset_has_emotional_context(self):
        from karpo_context.config import CONTEXT_CONFIGS

        personalized = CONTEXT_CONFIGS["personalized"]
        assert personalized.enable_emotional_context is True
        assert personalized.budget.emotional_context >= 200

    def test_planning_preset_has_large_budget(self):
        from karpo_context.config import CONTEXT_CONFIGS

        planning = CONTEXT_CONFIGS["planning"]
        # Planning mode needs more context for complex reasoning
        assert planning.budget.total_limit >= 16000
        assert planning.budget.recent_history >= 8000

    def test_get_config_returns_preset(self):
        from karpo_context.config import get_config

        config = get_config("fast")
        assert config.budget.total_limit == 4000

    def test_get_config_returns_default_for_unknown(self):
        from karpo_context.config import get_config

        config = get_config("unknown")
        # Should return default config
        assert config.budget.total_limit == 8000

    def test_get_config_with_none_returns_default(self):
        from karpo_context.config import get_config

        config = get_config(None)
        assert config.budget.total_limit == 8000


class TestContextConfigPriorities:
    """Tests for P0/P1/P2 priority configuration."""

    def test_config_has_priority_definitions(self):
        from karpo_context.config import ContextConfig

        config = ContextConfig()
        assert hasattr(config, "priority_order")
        assert "p0" in config.priority_order
        assert "p1" in config.priority_order
        assert "p2" in config.priority_order

    def test_priority_p0_includes_essential_components(self):
        from karpo_context.config import ContextConfig

        config = ContextConfig()
        p0 = config.priority_order["p0"]
        assert "persona" in p0
        assert "current_input" in p0

    def test_priority_p1_includes_important_components(self):
        from karpo_context.config import ContextConfig

        config = ContextConfig()
        p1 = config.priority_order["p1"]
        assert "response_instruction" in p1
        assert "conversation_summary" in p1
        assert "recent_history" in p1

    def test_priority_p2_includes_optional_components(self):
        from karpo_context.config import ContextConfig

        config = ContextConfig()
        p2 = config.priority_order["p2"]
        assert "emotional_context" in p2
