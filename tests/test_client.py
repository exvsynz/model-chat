import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from core.client import chat_stream, ChatError
from core.usage import UsageStats


@pytest.mark.asyncio
async def test_chat_stream_yields_tokens():
    mock_chunk_1 = MagicMock()
    mock_chunk_1.choices = [MagicMock()]
    mock_chunk_1.choices[0].delta.content = "Hello"
    mock_chunk_1.usage = None

    mock_chunk_2 = MagicMock()
    mock_chunk_2.choices = [MagicMock()]
    mock_chunk_2.choices[0].delta.content = " world"
    mock_chunk_2.usage = None

    mock_chunk_3 = MagicMock()
    mock_chunk_3.choices = [MagicMock()]
    mock_chunk_3.choices[0].delta.content = None
    mock_chunk_3.usage = None

    async def mock_stream():
        for chunk in [mock_chunk_1, mock_chunk_2, mock_chunk_3]:
            yield chunk

    with patch("core.client.get_async_openai_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_get_client.return_value = mock_client

        items = []
        async for item in chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/gpt-4o",
        ):
            items.append(item)

    tokens = [i for i in items if isinstance(i, str)]
    assert tokens == ["Hello", " world"]
    usage_items = [i for i in items if isinstance(i, UsageStats)]
    assert len(usage_items) == 1


@pytest.mark.asyncio
async def test_chat_stream_with_system_prompt():
    async def mock_stream():
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "ok"
        chunk.usage = None
        yield chunk

    with patch("core.client.get_async_openai_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_get_client.return_value = mock_client

        items = []
        async for item in chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/gpt-4o",
            system_prompt="You are helpful.",
        ):
            items.append(item)

        call_args = mock_client.chat.completions.create.call_args
        sent_messages = call_args.kwargs["messages"]
        assert sent_messages[0]["role"] == "system"
        assert sent_messages[0]["content"] == "You are helpful."


@pytest.mark.asyncio
async def test_chat_stream_with_effort():
    async def mock_stream():
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "ok"
        chunk.usage = None
        yield chunk

    with patch("core.client.get_async_openai_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_get_client.return_value = mock_client

        async for _ in chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            model="deepseek/deepseek-r1",
            effort="high",
        ):
            pass

        call_args = mock_client.chat.completions.create.call_args
        extra_body = call_args.kwargs.get("extra_body", {})
        assert extra_body.get("reasoning_effort") == "high"


def test_missing_api_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ChatError, match="OPENROUTER_API_KEY"):
            from core.client import get_async_openai_client
            get_async_openai_client()
