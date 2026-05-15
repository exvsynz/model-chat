import os
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from openai import AsyncOpenAI

from core.usage import UsageStats


class ChatError(Exception):
    pass


_client: AsyncOpenAI | None = None


def get_async_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ChatError("OPENROUTER_API_KEY environment variable not set")
        _client = AsyncOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    return _client


async def chat_stream(
    messages: list[dict],
    model: str,
    system_prompt: str | None = None,
    effort: str | None = None,
) -> AsyncGenerator[str | UsageStats, None]:
    client = get_async_openai_client()

    final_messages = []
    if system_prompt:
        final_messages.append({"role": "system", "content": system_prompt})
    final_messages.extend(messages)

    kwargs: dict = {
        "model": model,
        "messages": final_messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if effort:
        kwargs["extra_body"] = {"reasoning_effort": effort}

    start = time.monotonic()
    stream = await client.chat.completions.create(**kwargs)
    usage_data = None
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
        if hasattr(chunk, "usage") and chunk.usage:
            usage_data = chunk.usage

    elapsed = time.monotonic() - start
    prompt_tokens = getattr(usage_data, "prompt_tokens", 0) if usage_data else 0
    completion_tokens = getattr(usage_data, "completion_tokens", 0) if usage_data else 0
    yield UsageStats(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        elapsed_seconds=round(elapsed, 1),
    )


@dataclass
class ContentDelta:
    text: str


@dataclass
class ToolCallDelta:
    index: int
    id: str | None
    name: str | None
    arguments_chunk: str


@dataclass
class StreamEnd:
    usage: UsageStats
    finish_reason: str


async def stream_completion(
    messages: list[dict],
    model: str,
    system_prompt: str | None = None,
    tools: list[dict] | None = None,
    effort: str | None = None,
) -> AsyncGenerator[ContentDelta | ToolCallDelta | StreamEnd, None]:
    client = get_async_openai_client()

    final_messages = []
    if system_prompt:
        final_messages.append({"role": "system", "content": system_prompt})
    final_messages.extend(messages)

    kwargs: dict = {
        "model": model,
        "messages": final_messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        kwargs["tools"] = tools
    if effort:
        kwargs["extra_body"] = {"reasoning_effort": effort}

    start = time.monotonic()
    stream = await client.chat.completions.create(**kwargs)
    usage_data = None
    finish_reason = "stop"

    async for chunk in stream:
        if not chunk.choices:
            if hasattr(chunk, "usage") and chunk.usage:
                usage_data = chunk.usage
            continue

        delta = chunk.choices[0].delta
        fr = chunk.choices[0].finish_reason

        if fr:
            finish_reason = fr

        if delta.content:
            yield ContentDelta(text=delta.content)

        if delta.tool_calls:
            for tc in delta.tool_calls:
                yield ToolCallDelta(
                    index=tc.index,
                    id=tc.id,
                    name=tc.function.name if tc.function else None,
                    arguments_chunk=tc.function.arguments if tc.function else "",
                )

        if hasattr(chunk, "usage") and chunk.usage:
            usage_data = chunk.usage

    elapsed = time.monotonic() - start
    prompt_tokens = getattr(usage_data, "prompt_tokens", 0) if usage_data else 0
    completion_tokens = getattr(usage_data, "completion_tokens", 0) if usage_data else 0
    yield StreamEnd(
        usage=UsageStats(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            elapsed_seconds=round(elapsed, 1),
        ),
        finish_reason=finish_reason,
    )
