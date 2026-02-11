"""Tests for SessionState and ConversationSummary models."""

from datetime import datetime, timezone

from karpo_context.models import (
    SessionState,
    ConversationSummary,
    ChatMessage,
)


class TestConversationSummary:
    """Tests for ConversationSummary dataclass."""

    def test_create_summary(self):
        """Test creating a ConversationSummary."""
        summary = ConversationSummary(
            covers_until_turn=10,
            generated_at=datetime(2026, 2, 11, 10, 0, 0, tzinfo=timezone.utc),
            user_intent="规划东京 5 日游",
            key_entities={"destination": "东京", "duration": "5天"},
            decisions_made=["3月1日出发", "住新宿"],
            pending_questions=["是否需要 JR Pass"],
        )

        assert summary.covers_until_turn == 10
        assert summary.user_intent == "规划东京 5 日游"
        assert summary.key_entities["destination"] == "东京"
        assert len(summary.decisions_made) == 2
        assert len(summary.pending_questions) == 1
        assert summary.source_turn_range is None

    def test_summary_with_source_range(self):
        """Test summary with source turn range."""
        summary = ConversationSummary(
            covers_until_turn=10,
            generated_at=datetime.now(timezone.utc),
            user_intent="test",
            key_entities={},
            decisions_made=[],
            pending_questions=[],
            source_turn_range=(1, 10),
        )

        assert summary.source_turn_range == (1, 10)

    def test_summary_to_dict(self):
        """Test serialization to dict."""
        now = datetime(2026, 2, 11, 10, 0, 0, tzinfo=timezone.utc)
        summary = ConversationSummary(
            covers_until_turn=5,
            generated_at=now,
            user_intent="Book flight",
            key_entities={"dest": "Tokyo"},
            decisions_made=["March 1st"],
            pending_questions=["Need JR Pass?"],
            source_turn_range=(1, 5),
        )

        d = summary.to_dict()

        assert d["covers_until_turn"] == 5
        assert d["generated_at"] == now.isoformat()
        assert d["user_intent"] == "Book flight"
        assert d["key_entities"] == {"dest": "Tokyo"}
        assert d["decisions_made"] == ["March 1st"]
        assert d["pending_questions"] == ["Need JR Pass?"]
        assert d["source_turn_range"] == [1, 5]

    def test_summary_from_dict(self):
        """Test deserialization from dict."""
        d = {
            "covers_until_turn": 5,
            "generated_at": "2026-02-11T10:00:00+00:00",
            "user_intent": "Book flight",
            "key_entities": {"dest": "Tokyo"},
            "decisions_made": ["March 1st"],
            "pending_questions": ["Need JR Pass?"],
            "source_turn_range": [1, 5],
        }

        summary = ConversationSummary.from_dict(d)

        assert summary.covers_until_turn == 5
        assert summary.user_intent == "Book flight"
        assert summary.source_turn_range == (1, 5)

    def test_summary_from_dict_without_source_range(self):
        """Test deserialization without optional source_turn_range."""
        d = {
            "covers_until_turn": 5,
            "generated_at": "2026-02-11T10:00:00+00:00",
            "user_intent": "test",
            "key_entities": {},
            "decisions_made": [],
            "pending_questions": [],
        }

        summary = ConversationSummary.from_dict(d)
        assert summary.source_turn_range is None


class TestSessionState:
    """Tests for SessionState dataclass."""

    def test_create_session(self):
        """Test creating a SessionState."""
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=12345,
            user_id="user-001",
            created_at=now,
            updated_at=now,
        )

        assert session.thread_id == 12345
        assert session.user_id == "user-001"
        assert session.messages == []
        assert session.summary is None
        assert session.turn_count == 0

    def test_session_with_messages(self):
        """Test session with messages."""
        now = datetime.now(timezone.utc)
        msg = ChatMessage(
            role="user",
            content="Hello",
            created_at=now,
        )
        session = SessionState(
            thread_id=1,
            user_id="user-001",
            messages=[msg],
            turn_count=1,
            created_at=now,
            updated_at=now,
        )

        assert len(session.messages) == 1
        assert session.messages[0].content == "Hello"
        assert session.turn_count == 1

    def test_session_with_summary(self):
        """Test session with structured summary."""
        now = datetime.now(timezone.utc)
        summary = ConversationSummary(
            covers_until_turn=5,
            generated_at=now,
            user_intent="Plan trip",
            key_entities={"dest": "Tokyo"},
            decisions_made=[],
            pending_questions=[],
        )
        session = SessionState(
            thread_id=1,
            user_id="user-001",
            summary=summary,
            created_at=now,
            updated_at=now,
        )

        assert session.summary is not None
        assert session.summary.user_intent == "Plan trip"

    def test_add_message_increments_turn_for_user(self):
        """Test that adding user message increments turn count."""
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=1,
            user_id="user-001",
            created_at=now,
            updated_at=now,
        )

        session.add_message("user", "Hello")
        assert session.turn_count == 1
        assert len(session.messages) == 1

        session.add_message("assistant", "Hi there!")
        assert session.turn_count == 1  # Assistant doesn't increment
        assert len(session.messages) == 2

        session.add_message("user", "How are you?")
        assert session.turn_count == 2
        assert len(session.messages) == 3

    def test_add_message_with_tool_calls(self):
        """Test adding message with tool calls."""
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=1,
            user_id="user-001",
            created_at=now,
            updated_at=now,
        )

        tool_calls = [{"id": "call_1", "name": "weather", "args": {}}]
        session.add_message("assistant", None, tool_calls=tool_calls)

        assert len(session.messages) == 1
        assert session.messages[0].tool_calls == tool_calls

    def test_add_tool_result(self):
        """Test adding tool result message."""
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=1,
            user_id="user-001",
            created_at=now,
            updated_at=now,
        )

        session.add_message("tool", "Weather is sunny", tool_call_id="call_1")

        assert len(session.messages) == 1
        assert session.messages[0].role == "tool"
        assert session.messages[0].tool_call_id == "call_1"

    def test_session_to_dict(self):
        """Test serialization to dict."""
        now = datetime(2026, 2, 11, 10, 0, 0, tzinfo=timezone.utc)
        summary = ConversationSummary(
            covers_until_turn=5,
            generated_at=now,
            user_intent="Plan trip",
            key_entities={},
            decisions_made=[],
            pending_questions=[],
        )
        session = SessionState(
            thread_id=12345,
            user_id="user-001",
            summary=summary,
            turn_count=5,
            created_at=now,
            updated_at=now,
        )
        session.add_message("user", "Hello")

        d = session.to_dict()

        assert d["thread_id"] == 12345
        assert d["user_id"] == "user-001"
        assert d["turn_count"] == 6  # incremented by add_message
        assert d["summary"] is not None
        assert d["summary"]["user_intent"] == "Plan trip"
        assert len(d["messages"]) == 1

    def test_session_from_dict(self):
        """Test deserialization from dict."""
        d = {
            "thread_id": 12345,
            "user_id": "user-001",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                    "created_at": "2026-02-11T10:00:00+00:00",
                }
            ],
            "summary": {
                "covers_until_turn": 5,
                "generated_at": "2026-02-11T10:00:00+00:00",
                "user_intent": "Plan trip",
                "key_entities": {},
                "decisions_made": [],
                "pending_questions": [],
            },
            "turn_count": 5,
            "created_at": "2026-02-11T10:00:00+00:00",
            "updated_at": "2026-02-11T10:00:00+00:00",
        }

        session = SessionState.from_dict(d)

        assert session.thread_id == 12345
        assert session.user_id == "user-001"
        assert len(session.messages) == 1
        assert session.summary is not None
        assert session.summary.user_intent == "Plan trip"
        assert session.turn_count == 5

    def test_session_from_dict_without_summary(self):
        """Test deserialization without summary."""
        d = {
            "thread_id": 12345,
            "user_id": "user-001",
            "messages": [],
            "summary": None,
            "turn_count": 0,
            "created_at": "2026-02-11T10:00:00+00:00",
            "updated_at": "2026-02-11T10:00:00+00:00",
        }

        session = SessionState.from_dict(d)
        assert session.summary is None

    def test_session_summary_refs_and_error_refs(self):
        """Test session with summary_refs and error_refs lists."""
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=1,
            user_id="user-001",
            created_at=now,
            updated_at=now,
            summary_refs=["001", "002"],
            error_refs=["err_001"],
        )

        assert session.summary_refs == ["001", "002"]
        assert session.error_refs == ["err_001"]

    def test_session_to_dict_with_refs(self):
        """Test serialization includes refs."""
        now = datetime.now(timezone.utc)
        session = SessionState(
            thread_id=1,
            user_id="user-001",
            created_at=now,
            updated_at=now,
            summary_refs=["001"],
            error_refs=["err_001"],
        )

        d = session.to_dict()
        assert d["summary_refs"] == ["001"]
        assert d["error_refs"] == ["err_001"]
