"""LLM-based conversation summarizer."""
from collections.abc import Awaitable, Callable

from karpo_context.compaction.base import Summarizer
from karpo_context.models import ChatMessage

LLMCallable = Callable[[str], Awaitable[str]]

_DEFAULT_PROMPT_TEMPLATE = """\
Summarize the following conversation messages into a concise summary that captures \
the key information, decisions, and context needed to continue the conversation.

{existing_summary_section}\
Messages:
{messages}

Summary:"""

_EXISTING_SUMMARY_SECTION = """\
Previous summary to incorporate and update:
{existing_summary}

"""


class LLMSummarizer(Summarizer):
    """Summarizes messages using an LLM callable."""

    def __init__(
        self,
        llm_callable: LLMCallable,
        prompt_template: str | None = None,
    ) -> None:
        self._llm_callable = llm_callable
        self._prompt_template = prompt_template

    def _format_messages(self, messages: list[ChatMessage]) -> str:
        lines = []
        for msg in messages:
            content = msg.content or ""
            lines.append(f"{msg.role}: {content}")
        return "\n".join(lines)

    def _build_prompt(
        self,
        messages: list[ChatMessage],
        existing_summary: str | None = None,
    ) -> str:
        formatted_messages = self._format_messages(messages)

        if self._prompt_template is not None:
            return self._prompt_template.format(messages=formatted_messages)

        if existing_summary:
            existing_summary_section = _EXISTING_SUMMARY_SECTION.format(
                existing_summary=existing_summary
            )
        else:
            existing_summary_section = ""

        return _DEFAULT_PROMPT_TEMPLATE.format(
            existing_summary_section=existing_summary_section,
            messages=formatted_messages,
        )

    async def summarize(
        self,
        messages: list[ChatMessage],
        existing_summary: str | None = None,
    ) -> str:
        prompt = self._build_prompt(messages, existing_summary)
        return await self._llm_callable(prompt)
