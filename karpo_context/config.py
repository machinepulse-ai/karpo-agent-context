"""Context configuration and presets."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from karpo_context.budget import ContextBudget


@dataclass
class ContextConfig:
    """Configuration for context management.

    Includes budget allocation, compression settings, and priority definitions.
    """

    # Token budget configuration
    budget: ContextBudget = field(default_factory=ContextBudget)

    # Summary trigger settings
    summary_trigger_threshold: int = 20  # Trigger after N turns
    enable_proactive_summary: bool = True
    proactive_summary_threshold: float = 0.7  # Trigger at 70% capacity

    # Feature toggles
    enable_emotional_context: bool = True

    # Sliding window settings
    error_max_count: int = 50
    summary_backup_max_count: int = 20

    # Tool result offloading
    tool_result_offload_threshold: int = 500  # Tokens

    # Priority order for degradation
    priority_order: dict[str, list[str]] = field(default_factory=lambda: {
        "p0": ["persona", "current_input"],
        "p1": ["response_instruction", "conversation_summary", "recent_history"],
        "p2": ["emotional_context"],
    })


# Preset configurations for different use cases
CONTEXT_CONFIGS: dict[str, ContextConfig] = {
    "fast": ContextConfig(
        budget=ContextBudget(
            total_limit=4000,
            persona_prompt=500,
            response_instruction=300,
            conversation_summary=300,
            emotional_context=0,
            recent_history=2000,
            current_input=300,
            output_buffer=600,
        ),
        summary_trigger_threshold=10,
        enable_emotional_context=False,
        enable_proactive_summary=True,
        proactive_summary_threshold=0.6,
    ),
    "personalized": ContextConfig(
        budget=ContextBudget(
            total_limit=8000,
            persona_prompt=1200,
            response_instruction=500,
            conversation_summary=600,
            emotional_context=200,
            recent_history=4000,
            current_input=500,
            output_buffer=1000,
        ),
        summary_trigger_threshold=20,
        enable_emotional_context=True,
        enable_proactive_summary=True,
        proactive_summary_threshold=0.7,
    ),
    "planning": ContextConfig(
        budget=ContextBudget(
            total_limit=16000,
            persona_prompt=1500,
            response_instruction=800,
            conversation_summary=1000,
            emotional_context=200,
            recent_history=8000,
            current_input=1000,
            output_buffer=3500,
        ),
        summary_trigger_threshold=30,
        enable_emotional_context=True,
        enable_proactive_summary=True,
        proactive_summary_threshold=0.75,
    ),
}

# Default config (same as personalized)
_DEFAULT_CONFIG = ContextConfig()


def get_config(name: str | None) -> ContextConfig:
    """Get a context config by name.

    Args:
        name: Config preset name ("fast", "personalized", "planning")
              or None for default.

    Returns:
        The requested ContextConfig, or default if name not found.
    """
    if name is None:
        return _DEFAULT_CONFIG
    return CONTEXT_CONFIGS.get(name, _DEFAULT_CONFIG)
