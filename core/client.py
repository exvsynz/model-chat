import os
import time
from collections.abc import AsyncGenerator
from openai import AsyncOpenAI
from core.usage import UsageStats


class ChatError(Exception):
    pass


def get_async_openai_client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ChatError("OPENROUTER_API_KEY environment variable not set")
    return AsyncOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")


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
