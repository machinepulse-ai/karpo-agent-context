# karpo-context

Agent 会话上下文管理 SDK。提供上下文的存储、加载和自动压缩能力，后端基于 AWS ElastiCache (Redis)。

## Architecture

<p align="center">
  <img src="docs/architecture.svg" alt="Architecture" width="600" />
</p>

## Installation

```bash
# 作为依赖引入（推荐通过 git 安装）
uv add git+ssh://git@github.com/machinepulse-ai/karpo-agent-context.git

# 或本地开发
uv pip install -e .
```

Requirements: Python >= 3.12

## Quick Start

```python
from karpo_context import create_context_store, ContextManager

# 一行初始化，内置 ElastiCache endpoint，无需传参
store = create_context_store()
manager = ContextManager(store=store)

# 加载/创建会话
ctx = await manager.load(conversation_id=42)

# 追加消息（自动持久化）
from datetime import datetime, timezone
from karpo_context import ChatMessage

msg = ChatMessage(role="user", content="你好", created_at=datetime.now(timezone.utc))
ctx = await manager.append_message(conversation_id=42, message=msg)

# 用完关闭连接
await store.close()
```

## Configuration

`create_context_store()` 的 Redis URL 解析优先级：

| 优先级 | 来源 | 示例 |
|--------|------|------|
| 1 | 显式参数 `url` | `create_context_store(url="rediss://...")` |
| 2 | 环境变量 `KARPO_CONTEXT_REDIS_URL` | `export KARPO_CONTEXT_REDIS_URL=rediss://...` |
| 3 | 内置默认值 | ElastiCache staging endpoint |

也可以直接通过 `RedisContextStore.from_url()` 自行初始化：

```python
from karpo_context import RedisContextStore

store = RedisContextStore.from_url(
    "rediss://master.karpo-context-cache.wimmex.use1.cache.amazonaws.com:6379",
    prefix="karpo:ctx",       # key 前缀，默认 karpo:ctx
    ttl_seconds=7 * 24 * 3600, # 过期时间，默认 7 天
)
```

## Auto-Compaction

当消息数超过阈值时，自动将旧消息通过 LLM 压缩为摘要，只保留最近 N 条消息。

```python
from karpo_context import (
    ContextManager,
    MessageCountTrigger,
    LLMSummarizer,
    create_context_store,
)

async def call_llm(prompt: str) -> str:
    # 对接你的 LLM 服务
    ...

store = create_context_store()
manager = ContextManager(
    store=store,
    trigger=MessageCountTrigger(threshold=50),   # 超过 50 条触发压缩
    summarizer=LLMSummarizer(llm_callable=call_llm),
    keep_recent=10,                               # 保留最近 10 条
)
```

## Data Model

`ConversationContext` 包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `conversation_id` | `int` | 会话唯一标识 |
| `messages` | `list[ChatMessage]` | 消息列表 |
| `summary` | `str \| None` | 旧消息压缩摘要 |
| `persona` | `dict \| None` | Agent 角色定义 |
| `tool_call_history` | `list[ToolCallRecord]` | 工具调用记录 |
| `phase` | `str` | 当前对话阶段 |
| `intent` | `str \| None` | 用户意图 |
| `slots` / `missing_slots` | `dict` / `list` | 槽位填充状态 |
| `message_count` | `int` | 消息计数 |

## Development

```bash
# 安装开发依赖
uv sync --group dev

# 运行测试
uv run pytest -v
```
