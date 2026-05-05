import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.agent import AgentLoop, TextDelta, ToolCallStart, ToolResult, Finished
from core.client import ContentDelta, ToolCallDelta, StreamEnd
from core.usage import UsageStats


@pytest.mark.asyncio
async def test_agent_loop_text_only():
    """AgentLoop yields TextDelta and Finished for a plain text response."""
    async def mock_stream(*a, **kw):
        yield ContentDelta(text="Hello ")
        yield ContentDelta(text="world")
        yield StreamEnd(
            usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=1.0),
            finish_reason="stop",
        )

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        from core.tools import create_default_registry
        from pathlib import Path
        registry = create_default_registry(work_dir=Path("."))

        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "hi"}],
            system_prompt=None,
            tools=registry,
            permission_fn=AsyncMock(return_value=True),
        )

        events = []
        async for event in loop.run():
            events.append(event)

    text_events = [e for e in events if isinstance(e, TextDelta)]
    assert len(text_events) == 2
    assert text_events[0].content == "Hello "
    assert text_events[1].content == "world"

    finished_events = [e for e in events if isinstance(e, Finished)]
    assert len(finished_events) == 1
    assert finished_events[0].usage.total_tokens == 15


@pytest.mark.asyncio
async def test_agent_loop_tool_call_then_text():
    """AgentLoop handles tool call, executes it, and loops for final response."""
    call_count = 0

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield ToolCallDelta(index=0, id="call_1", name="read_file", arguments_chunk='{"path":')
            yield ToolCallDelta(index=0, id=None, name=None, arguments_chunk=' "test.txt"}')
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=0.5),
                finish_reason="tool_calls",
            )
        else:
            yield ContentDelta(text="File contains hello")
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=20, completion_tokens=10, total_tokens=30, elapsed_seconds=0.5),
                finish_reason="stop",
            )

    async def mock_execute(name, arguments):
        return "hello"

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = [{"type": "function", "function": {"name": "read_file", "parameters": {}}}]
    mock_registry.needs_permission.return_value = False
    mock_registry.execute = AsyncMock(side_effect=mock_execute)

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "read test.txt"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=AsyncMock(return_value=True),
        )

        events = []
        async for event in loop.run():
            events.append(event)

    tool_starts = [e for e in events if isinstance(e, ToolCallStart)]
    assert len(tool_starts) == 1
    assert tool_starts[0].name == "read_file"
    assert tool_starts[0].arguments == {"path": "test.txt"}

    tool_results = [e for e in events if isinstance(e, ToolResult)]
    assert len(tool_results) == 1
    assert tool_results[0].output == "hello"
    assert tool_results[0].is_error is False

    text_events = [e for e in events if isinstance(e, TextDelta)]
    assert text_events[0].content == "File contains hello"


@pytest.mark.asyncio
async def test_agent_loop_permission_denied():
    """AgentLoop sends error when permission is denied."""
    call_count = 0

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield ToolCallDelta(index=0, id="call_1", name="bash", arguments_chunk='{"command": "rm -rf /"}')
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=0.5),
                finish_reason="tool_calls",
            )
        else:
            yield ContentDelta(text="Understood, I won't do that.")
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=20, completion_tokens=10, total_tokens=30, elapsed_seconds=0.5),
                finish_reason="stop",
            )

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = []
    mock_registry.needs_permission.return_value = True
    mock_registry.execute = AsyncMock()

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "delete everything"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=AsyncMock(return_value=False),
        )

        events = []
        async for event in loop.run():
            events.append(event)

    tool_results = [e for e in events if isinstance(e, ToolResult)]
    assert len(tool_results) == 1
    assert tool_results[0].is_error is True
    assert "denied" in tool_results[0].output.lower()

    mock_registry.execute.assert_not_called()
