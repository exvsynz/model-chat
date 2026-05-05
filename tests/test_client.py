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


@pytest.mark.asyncio
async def test_stream_completion_content_only():
    """stream_completion yields ContentDelta for text and StreamEnd at the end."""
    from core.client import stream_completion, ContentDelta, StreamEnd

    mock_chunk_1 = MagicMock()
    mock_chunk_1.choices = [MagicMock()]
    mock_chunk_1.choices[0].delta.content = "Hello"
    mock_chunk_1.choices[0].delta.tool_calls = None
    mock_chunk_1.choices[0].finish_reason = None
    mock_chunk_1.usage = None

    mock_chunk_2 = MagicMock()
    mock_chunk_2.choices = [MagicMock()]
    mock_chunk_2.choices[0].delta.content = " world"
    mock_chunk_2.choices[0].delta.tool_calls = None
    mock_chunk_2.choices[0].finish_reason = None
    mock_chunk_2.usage = None

    mock_chunk_3 = MagicMock()
    mock_chunk_3.choices = [MagicMock()]
    mock_chunk_3.choices[0].delta.content = None
    mock_chunk_3.choices[0].delta.tool_calls = None
    mock_chunk_3.choices[0].finish_reason = "stop"
    mock_chunk_3.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    async def mock_stream():
        for chunk in [mock_chunk_1, mock_chunk_2, mock_chunk_3]:
            yield chunk

    with patch("core.client.get_async_openai_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_get_client.return_value = mock_client

        events = []
        async for event in stream_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/gpt-4o",
        ):
            events.append(event)

    content_events = [e for e in events if isinstance(e, ContentDelta)]
    assert len(content_events) == 2
    assert content_events[0].text == "Hello"
    assert content_events[1].text == " world"

    end_events = [e for e in events if isinstance(e, StreamEnd)]
    assert len(end_events) == 1
    assert end_events[0].finish_reason == "stop"
    assert end_events[0].usage.total_tokens == 15


@pytest.mark.asyncio
async def test_stream_completion_tool_calls():
    """stream_completion yields ToolCallDelta for tool call chunks."""
    from core.client import stream_completion, ToolCallDelta, StreamEnd

    mock_tc_delta_1 = MagicMock()
    mock_tc_delta_1.index = 0
    mock_tc_delta_1.id = "call_abc123"
    mock_tc_delta_1.function.name = "read_file"
    mock_tc_delta_1.function.arguments = '{"path":'

    mock_tc_delta_2 = MagicMock()
    mock_tc_delta_2.index = 0
    mock_tc_delta_2.id = None
    mock_tc_delta_2.function.name = None
    mock_tc_delta_2.function.arguments = ' "src/main.py"}'

    mock_chunk_1 = MagicMock()
    mock_chunk_1.choices = [MagicMock()]
    mock_chunk_1.choices[0].delta.content = None
    mock_chunk_1.choices[0].delta.tool_calls = [mock_tc_delta_1]
    mock_chunk_1.choices[0].finish_reason = None
    mock_chunk_1.usage = None

    mock_chunk_2 = MagicMock()
    mock_chunk_2.choices = [MagicMock()]
    mock_chunk_2.choices[0].delta.content = None
    mock_chunk_2.choices[0].delta.tool_calls = [mock_tc_delta_2]
    mock_chunk_2.choices[0].finish_reason = None
    mock_chunk_2.usage = None

    mock_chunk_3 = MagicMock()
    mock_chunk_3.choices = [MagicMock()]
    mock_chunk_3.choices[0].delta.content = None
    mock_chunk_3.choices[0].delta.tool_calls = None
    mock_chunk_3.choices[0].finish_reason = "tool_calls"
    mock_chunk_3.usage = MagicMock(prompt_tokens=20, completion_tokens=10)

    async def mock_stream():
        for chunk in [mock_chunk_1, mock_chunk_2, mock_chunk_3]:
            yield chunk

    with patch("core.client.get_async_openai_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_get_client.return_value = mock_client

        events = []
        async for event in stream_completion(
            messages=[{"role": "user", "content": "read src/main.py"}],
            model="openai/gpt-4o",
            tools=[{"type": "function", "function": {"name": "read_file", "parameters": {}}}],
        ):
            events.append(event)

    tc_events = [e for e in events if isinstance(e, ToolCallDelta)]
    assert len(tc_events) == 2
    assert tc_events[0].id == "call_abc123"
    assert tc_events[0].name == "read_file"
    assert tc_events[0].arguments_chunk == '{"path":'
    assert tc_events[1].id is None
    assert tc_events[1].arguments_chunk == ' "src/main.py"}'

    end_events = [e for e in events if isinstance(e, StreamEnd)]
    assert end_events[0].finish_reason == "tool_calls"
