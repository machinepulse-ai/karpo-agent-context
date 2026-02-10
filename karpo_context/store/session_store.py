"""Session state storage with Redis backend."""
from __future__ import annotations

import json
import ssl
from typing import Any

from redis.asyncio import Redis

from karpo_context.models import SessionState
from karpo_context.store.base import ContextStore


class SessionStateStore(ContextStore):
    """Stores SessionState in Redis with agent-specific key namespacing.

    Key formats:
    - Session: ctx:{agent}:session:{thread_id}
    - Tool result: ctx:{agent}:tool:{thread_id}:{call_id}
    - Errors: ctx:{agent}:errors:{thread_id} (list)
    - Summary backup: ctx:{agent}:summary_backup:{thread_id} (list)
    """

    def __init__(
        self,
        redis_client: Redis,
        agent_name: str,
        ttl_seconds: int = 7 * 24 * 3600,
        error_max_count: int = 50,
        summary_backup_max_count: int = 20,
    ) -> None:
        self._redis = redis_client
        self._agent_name = agent_name
        self._ttl_seconds = ttl_seconds
        self._error_max_count = error_max_count
        self._summary_backup_max_count = summary_backup_max_count

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        agent_name: str,
        ttl_seconds: int = 7 * 24 * 3600,
        error_max_count: int = 50,
        summary_backup_max_count: int = 20,
        ssl_cert_reqs: str | None = None,
        **redis_kwargs: Any,
    ) -> SessionStateStore:
        """Create a store from a Redis URL.

        Args:
            url: Redis connection URL (redis:// or rediss://).
            agent_name: Agent identifier for key namespacing.
            ttl_seconds: Time-to-live for stored data.
            error_max_count: Max errors to keep in sliding window.
            summary_backup_max_count: Max summary backups to keep.
            ssl_cert_reqs: SSL verification mode ("none" to skip).
            **redis_kwargs: Extra args for Redis.from_url().
        """
        kwargs: dict[str, Any] = {**redis_kwargs}

        if url.startswith("rediss://"):
            ssl_ctx = ssl.create_default_context()
            if ssl_cert_reqs == "none":
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
            kwargs.setdefault("ssl", True)
            kwargs.setdefault("ssl_context", ssl_ctx)

        client = Redis.from_url(url, **kwargs)
        return cls(
            client,
            agent_name=agent_name,
            ttl_seconds=ttl_seconds,
            error_max_count=error_max_count,
            summary_backup_max_count=summary_backup_max_count,
        )

    async def close(self) -> None:
        """Close the underlying Redis connection."""
        await self._redis.aclose()

    def _session_key(self, thread_id: int) -> str:
        return f"ctx:{self._agent_name}:session:{thread_id}"

    def _tool_key(self, thread_id: int, call_id: str) -> str:
        return f"ctx:{self._agent_name}:tool:{thread_id}:{call_id}"

    def _errors_key(self, thread_id: int) -> str:
        return f"ctx:{self._agent_name}:errors:{thread_id}"

    def _summary_backup_key(self, thread_id: int) -> str:
        return f"ctx:{self._agent_name}:summary_backup:{thread_id}"

    async def get(self, thread_id: int) -> SessionState | None:
        """Get session state by thread ID."""
        raw = await self._redis.get(self._session_key(thread_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return SessionState.from_dict(data)

    async def save(self, session: SessionState) -> None:
        """Save session state."""
        key = self._session_key(session.thread_id)
        data = json.dumps(session.to_dict())
        await self._redis.set(key, data, ex=self._ttl_seconds)

    async def delete(self, thread_id: int) -> None:
        """Delete session state."""
        await self._redis.delete(self._session_key(thread_id))

    async def save_tool_result(
        self, thread_id: int, call_id: str, result: Any
    ) -> None:
        """Save a tool call result for later retrieval.

        Used for offloading large tool results (>500 tokens) from
        the main session to reduce context size.
        """
        key = self._tool_key(thread_id, call_id)
        data = json.dumps(result)
        await self._redis.set(key, data, ex=self._ttl_seconds)

    async def get_tool_result(self, thread_id: int, call_id: str) -> Any | None:
        """Get a stored tool result."""
        raw = await self._redis.get(self._tool_key(thread_id, call_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def append_error(self, thread_id: int, error: dict[str, Any]) -> None:
        """Append an error to the error notebook (sliding window).

        Maintains a sliding window of the most recent errors.
        """
        key = self._errors_key(thread_id)
        data = json.dumps(error)
        async with self._redis.pipeline() as pipe:
            pipe.rpush(key, data)
            pipe.ltrim(key, -self._error_max_count, -1)
            pipe.expire(key, self._ttl_seconds)
            await pipe.execute()

    async def get_errors(self, thread_id: int) -> list[dict[str, Any]]:
        """Get all errors from the error notebook."""
        key = self._errors_key(thread_id)
        raw_list = await self._redis.lrange(key, 0, -1)
        return [json.loads(item) for item in raw_list]

    async def save_summary_backup(
        self, thread_id: int, backup: dict[str, Any]
    ) -> None:
        """Save a summary backup with original messages.

        Used to store original messages when generating summaries,
        allowing retrospection if needed.
        """
        key = self._summary_backup_key(thread_id)
        data = json.dumps(backup)
        async with self._redis.pipeline() as pipe:
            pipe.rpush(key, data)
            pipe.ltrim(key, -self._summary_backup_max_count, -1)
            pipe.expire(key, self._ttl_seconds)
            await pipe.execute()

    async def get_summary_backups(self, thread_id: int) -> list[dict[str, Any]]:
        """Get all summary backups."""
        key = self._summary_backup_key(thread_id)
        raw_list = await self._redis.lrange(key, 0, -1)
        return [json.loads(item) for item in raw_list]
