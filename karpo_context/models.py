"""Data models for conversation context."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ChatMessage:
    """A single message in a conversation."""

    role: str
    content: str | None
    created_at: datetime
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }
        if self.name is not None:
            d["name"] = self.name
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ChatMessage":
        return cls(
            role=d["role"],
            content=d["content"],
            created_at=datetime.fromisoformat(d["created_at"]),
            name=d.get("name"),
            tool_call_id=d.get("tool_call_id"),
            tool_calls=d.get("tool_calls"),
        )


@dataclass
class ToolCallRecord:
    """Record of a tool call execution."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any
    called_at: datetime
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "called_at": self.called_at.isoformat(),
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ToolCallRecord":
        return cls(
            tool_name=d["tool_name"],
            arguments=d["arguments"],
            result=d["result"],
            called_at=datetime.fromisoformat(d["called_at"]),
            duration_ms=d["duration_ms"],
        )


@dataclass
class ConversationContext:
    """Full context for a conversation."""

    conversation_id: int
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessage] = field(default_factory=list)
    summary: str | None = None
    persona: dict[str, Any] | None = None
    loaded_tools: list[str] = field(default_factory=list)
    loaded_skills: list[str] = field(default_factory=list)
    tool_call_history: list[ToolCallRecord] = field(default_factory=list)
    phase: str = "idle"
    slots: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    intent: str | None = None
    message_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [m.to_dict() for m in self.messages],
            "summary": self.summary,
            "persona": self.persona,
            "loaded_tools": self.loaded_tools,
            "loaded_skills": self.loaded_skills,
            "tool_call_history": [t.to_dict() for t in self.tool_call_history],
            "phase": self.phase,
            "slots": self.slots,
            "missing_slots": self.missing_slots,
            "intent": self.intent,
            "message_count": self.message_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ConversationContext":
        return cls(
            conversation_id=d["conversation_id"],
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
            messages=[ChatMessage.from_dict(m) for m in d.get("messages", [])],
            summary=d.get("summary"),
            persona=d.get("persona"),
            loaded_tools=d.get("loaded_tools", []),
            loaded_skills=d.get("loaded_skills", []),
            tool_call_history=[
                ToolCallRecord.from_dict(t)
                for t in d.get("tool_call_history", [])
            ],
            phase=d.get("phase", "idle"),
            slots=d.get("slots", {}),
            missing_slots=d.get("missing_slots", []),
            intent=d.get("intent"),
            message_count=d.get("message_count", 0),
        )
