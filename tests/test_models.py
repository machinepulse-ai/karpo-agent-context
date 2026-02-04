"""Tests for karpo_context.models data classes."""
from datetime import datetime, timezone


class TestChatMessage:
    def test_create_user_message(self):
        from karpo_context.models import ChatMessage

        now = datetime.now(timezone.utc)
        msg = ChatMessage(role="user", content="Hello", created_at=now)
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.created_at == now
        assert msg.name is None
        assert msg.tool_call_id is None
        assert msg.tool_calls is None

    def test_create_tool_message(self):
        from karpo_context.models import ChatMessage

        now = datetime.now(timezone.utc)
        msg = ChatMessage(
            role="tool",
            content='{"result": 42}',
            created_at=now,
            tool_call_id="call_abc123",
        )
        assert msg.tool_call_id == "call_abc123"

    def test_create_message_with_tool_calls(self):
        from karpo_context.models import ChatMessage

        now = datetime.now(timezone.utc)
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city":"NYC"}'},
            }
        ]
        msg = ChatMessage(
            role="assistant", content=None, created_at=now, tool_calls=tool_calls
        )
        assert msg.tool_calls == tool_calls

    def test_chat_message_to_dict_and_from_dict(self):
        from karpo_context.models import ChatMessage

        now = datetime.now(timezone.utc)
        msg = ChatMessage(role="user", content="test", created_at=now)
        d = msg.to_dict()
        assert d["role"] == "user"
        restored = ChatMessage.from_dict(d)
        assert restored.role == "user"
        assert restored.created_at == now


class TestToolCallRecord:
    def test_create_and_roundtrip(self):
        from karpo_context.models import ToolCallRecord

        now = datetime.now(timezone.utc)
        record = ToolCallRecord(
            tool_name="search",
            arguments={"q": "hi"},
            result="found",
            called_at=now,
            duration_ms=50,
        )
        d = record.to_dict()
        assert d["tool_name"] == "search"
        restored = ToolCallRecord.from_dict(d)
        assert restored.called_at == now


class TestConversationContext:
    def test_create_default(self):
        from karpo_context.models import ConversationContext

        now = datetime.now(timezone.utc)
        ctx = ConversationContext(
            conversation_id=42, created_at=now, updated_at=now
        )
        assert ctx.messages == []
        assert ctx.summary is None
        assert ctx.phase == "idle"
        assert ctx.message_count == 0

    def test_full_roundtrip(self):
        from karpo_context.models import (
            ChatMessage,
            ConversationContext,
            ToolCallRecord,
        )

        now = datetime.now(timezone.utc)
        ctx = ConversationContext(
            conversation_id=99,
            messages=[
                ChatMessage(role="user", content="Hello", created_at=now)
            ],
            summary="A greeting",
            persona={"name": "Agent"},
            loaded_tools=["greet"],
            loaded_skills=["chat"],
            tool_call_history=[
                ToolCallRecord(
                    tool_name="greet",
                    arguments={},
                    result="Hi!",
                    called_at=now,
                    duration_ms=10,
                )
            ],
            phase="confirming",
            slots={"name": "Alice"},
            missing_slots=["age"],
            intent="greet_user",
            created_at=now,
            updated_at=now,
            message_count=1,
        )
        d = ctx.to_dict()
        restored = ConversationContext.from_dict(d)
        assert restored.conversation_id == 99
        assert restored.summary == "A greeting"
        assert len(restored.messages) == 1
        assert len(restored.tool_call_history) == 1
