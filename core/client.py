import os
from collections.abc import AsyncGenerator
from openai import OpenAI


class ChatError(Exception):
    pass


def get_openai_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ChatError("OPENROUTER_API_KEY environment variable not set")
    return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")


async def chat_stream(
    messages: list[dict],
    model: str,
    system_prompt: str | None = None,
    effort: str | None = None,
) -> AsyncGenerator[str, None]:
    client = get_openai_client()

    final_messages = []
    if system_prompt:
        final_messages.append({"role": "system", "content": system_prompt})
    final_messages.extend(messages)

    kwargs: dict = {
        "model": model,
        "messages": final_messages,
        "stream": True,
    }
    if effort:
        kwargs["extra_body"] = {"reasoning_effort": effort}

    stream = client.chat.completions.create(**kwargs)
    if hasattr(stream, "__aiter__"):
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    else:
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
