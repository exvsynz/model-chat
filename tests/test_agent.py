import asyncio
import json
import os
import pytest
from pathlib import Path
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
            yield ToolCallDelta(index=0, id="call_1", name="shell", arguments_chunk='{"command": "rm -rf /"}')
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


@pytest.mark.asyncio
async def test_agent_loop_web_search_integration():
    """AgentLoop calls web_search tool and synthesizes a response from results."""
    call_count = 0

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield ToolCallDelta(
                index=0, id="call_ws", name="web_search",
                arguments_chunk='{"query": "latest news today"}',
            )
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=20, completion_tokens=10, total_tokens=30, elapsed_seconds=0.5),
                finish_reason="tool_calls",
            )
        else:
            yield ContentDelta(text="Based on the search results, here is the latest news.")
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=50, completion_tokens=20, total_tokens=70, elapsed_seconds=1.0),
                finish_reason="stop",
            )

    brave_response = {
        "web": {
            "results": [
                {"title": "Breaking News", "url": "https://news.example.com", "description": "Something happened today"},
            ]
        }
    }

    mock_resp = AsyncMock()
    mock_resp.json = lambda: brave_response
    mock_resp.raise_for_status = lambda: None

    from core.tools import create_default_registry
    registry = create_default_registry(work_dir=Path("."))

    with patch("core.agent.stream_completion", side_effect=mock_stream), \
         patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"}), \
         patch("core.tools.httpx.AsyncClient") as mock_client_cls:

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "What happened in the news today?"}],
            system_prompt=None,
            tools=registry,
            permission_fn=AsyncMock(return_value=True),
        )

        events = []
        async for event in loop.run():
            events.append(event)

    tool_starts = [e for e in events if isinstance(e, ToolCallStart)]
    assert len(tool_starts) == 1
    assert tool_starts[0].name == "web_search"

    tool_results = [e for e in events if isinstance(e, ToolResult)]
    assert len(tool_results) == 1
    assert "Breaking News" in tool_results[0].output
    assert tool_results[0].is_error is False

    text_events = [e for e in events if isinstance(e, TextDelta)]
    assert any("search results" in e.content.lower() for e in text_events)

    finished = [e for e in events if isinstance(e, Finished)]
    assert len(finished) == 1
    assert finished[0].usage.total_tokens == 100


@pytest.mark.asyncio
async def test_agent_loop_web_search_auto_approved():
    """web_search has auto permission and doesn't require user approval."""
    from core.tools import create_default_registry
    registry = create_default_registry(work_dir=Path("."))
    assert not registry.needs_permission("web_search")


@pytest.mark.asyncio
async def test_agent_loop_no_tool_support_fallback():
    """Models that don't call tools still produce a normal text response."""
    async def mock_stream(*a, **kw):
        yield ContentDelta(text="I don't have access to current information, but ")
        yield ContentDelta(text="here's what I know.")
        yield StreamEnd(
            usage=UsageStats(prompt_tokens=15, completion_tokens=10, total_tokens=25, elapsed_seconds=0.8),
            finish_reason="stop",
        )

    from core.tools import create_default_registry
    registry = create_default_registry(work_dir=Path("."))

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model-no-tools",
            messages=[{"role": "user", "content": "What's the news?"}],
            system_prompt=None,
            tools=registry,
            permission_fn=AsyncMock(return_value=True),
        )

        events = []
        async for event in loop.run():
            events.append(event)

    tool_starts = [e for e in events if isinstance(e, ToolCallStart)]
    assert len(tool_starts) == 0

    text_events = [e for e in events if isinstance(e, TextDelta)]
    assert len(text_events) == 2

    finished = [e for e in events if isinstance(e, Finished)]
    assert len(finished) == 1


@pytest.mark.asyncio
async def test_agent_loop_max_iterations():
    """AgentLoop stops after max_iterations and reports it."""
    async def mock_stream(*a, **kw):
        yield ToolCallDelta(index=0, id="call_loop", name="read_file", arguments_chunk='{"path": "x.txt"}')
        yield StreamEnd(
            usage=UsageStats(prompt_tokens=5, completion_tokens=3, total_tokens=8, elapsed_seconds=0.1),
            finish_reason="tool_calls",
        )

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = []
    mock_registry.needs_permission.return_value = False
    mock_registry.execute = AsyncMock(return_value="content")

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "loop forever"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=AsyncMock(return_value=True),
            max_iterations=3,
        )

        events = []
        async for event in loop.run():
            events.append(event)

    finished = [e for e in events if isinstance(e, Finished)]
    assert len(finished) == 1
    assert finished[0].stop_reason == "max_iterations"

    text_events = [e for e in events if isinstance(e, TextDelta)]
    assert any("max iterations" in e.content for e in text_events)

    tool_starts = [e for e in events if isinstance(e, ToolCallStart)]
    assert len(tool_starts) == 3


@pytest.mark.asyncio
async def test_agent_loop_timeout():
    """AgentLoop stops after timeout_seconds."""
    call_count = 0

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        yield ToolCallDelta(index=0, id=f"call_{call_count}", name="shell", arguments_chunk='{"command": "sleep 1"}')
        yield StreamEnd(
            usage=UsageStats(prompt_tokens=5, completion_tokens=3, total_tokens=8, elapsed_seconds=0.1),
            finish_reason="tool_calls",
        )

    async def slow_execute(name, arguments):
        await asyncio.sleep(0.2)
        return "done"

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = []
    mock_registry.needs_permission.return_value = False
    mock_registry.execute = AsyncMock(side_effect=slow_execute)

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "slow loop"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=AsyncMock(return_value=True),
            timeout_seconds=0.5,
            max_iterations=100,
        )

        events = []
        async for event in loop.run():
            events.append(event)

    finished = [e for e in events if isinstance(e, Finished)]
    assert len(finished) == 1
    assert finished[0].stop_reason == "timeout"


@pytest.mark.asyncio
async def test_agent_loop_abort():
    """AgentLoop stops when abort_event is set mid-execution."""
    call_count = 0
    abort_event = asyncio.Event()

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        yield ToolCallDelta(index=0, id=f"call_{call_count}", name="read_file", arguments_chunk='{"path": "x.txt"}')
        yield StreamEnd(
            usage=UsageStats(prompt_tokens=5, completion_tokens=3, total_tokens=8, elapsed_seconds=0.1),
            finish_reason="tool_calls",
        )

    async def execute_then_abort(name, arguments):
        if call_count >= 2:
            abort_event.set()
        return "content"

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = []
    mock_registry.needs_permission.return_value = False
    mock_registry.execute = AsyncMock(side_effect=execute_then_abort)

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "abort me"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=AsyncMock(return_value=True),
            abort_event=abort_event,
            max_iterations=100,
        )

        events = []
        async for event in loop.run():
            events.append(event)

    finished = [e for e in events if isinstance(e, Finished)]
    assert len(finished) == 1
    assert finished[0].stop_reason == "aborted"

    text_events = [e for e in events if isinstance(e, TextDelta)]
    assert any("aborted" in e.content.lower() for e in text_events)


@pytest.mark.asyncio
async def test_agent_loop_parallel_tool_execution():
    """Multiple tool calls in one turn execute concurrently."""
    call_count = 0

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield ToolCallDelta(index=0, id="call_a", name="read_file", arguments_chunk='{"path": "a.txt"}')
            yield ToolCallDelta(index=1, id="call_b", name="read_file", arguments_chunk='{"path": "b.txt"}')
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=0.2),
                finish_reason="tool_calls",
            )
        else:
            yield ContentDelta(text="Got both files")
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=20, completion_tokens=10, total_tokens=30, elapsed_seconds=0.2),
                finish_reason="stop",
            )

    execution_times = []

    async def timed_execute(name, arguments):
        start = time.monotonic()
        await asyncio.sleep(0.2)
        execution_times.append(time.monotonic() - start)
        return f"content of {arguments['path']}"

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = []
    mock_registry.needs_permission.return_value = False
    mock_registry.execute = AsyncMock(side_effect=timed_execute)

    import time
    with patch("core.agent.stream_completion", side_effect=mock_stream):
        overall_start = time.monotonic()
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "read both files"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=AsyncMock(return_value=True),
        )

        events = []
        async for event in loop.run():
            events.append(event)
        overall_elapsed = time.monotonic() - overall_start

    tool_starts = [e for e in events if isinstance(e, ToolCallStart)]
    assert len(tool_starts) == 2
    assert tool_starts[0].id == "call_a"
    assert tool_starts[1].id == "call_b"

    tool_results = [e for e in events if isinstance(e, ToolResult)]
    assert len(tool_results) == 2
    assert tool_results[0].id == "call_a"
    assert tool_results[1].id == "call_b"
    assert "a.txt" in tool_results[0].output
    assert "b.txt" in tool_results[1].output

    # Concurrent: 2 x 0.2s tasks should complete in ~0.2s, not ~0.4s
    assert overall_elapsed < 0.8


@pytest.mark.asyncio
async def test_agent_loop_parallel_one_fails():
    """One failing tool doesn't block other concurrent tools."""
    call_count = 0

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield ToolCallDelta(index=0, id="call_ok", name="read_file", arguments_chunk='{"path": "good.txt"}')
            yield ToolCallDelta(index=1, id="call_fail", name="read_file", arguments_chunk='{"path": "bad.txt"}')
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=0.2),
                finish_reason="tool_calls",
            )
        else:
            yield ContentDelta(text="One worked, one failed")
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=20, completion_tokens=10, total_tokens=30, elapsed_seconds=0.2),
                finish_reason="stop",
            )

    async def execute_with_failure(name, arguments):
        if arguments.get("path") == "bad.txt":
            return "Error: file not found"
        return "good content"

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = []
    mock_registry.needs_permission.return_value = False
    mock_registry.execute = AsyncMock(side_effect=execute_with_failure)

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "read both"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=AsyncMock(return_value=True),
        )

        events = []
        async for event in loop.run():
            events.append(event)

    tool_results = [e for e in events if isinstance(e, ToolResult)]
    assert len(tool_results) == 2
    assert tool_results[0].is_error is False
    assert tool_results[0].output == "good content"
    assert tool_results[1].is_error is True
    assert "not found" in tool_results[1].output


@pytest.mark.asyncio
async def test_agent_loop_parallel_permission_sequential():
    """Permission checks happen sequentially even in parallel mode."""
    call_count = 0
    permission_order = []

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield ToolCallDelta(index=0, id="call_1", name="shell", arguments_chunk='{"command": "ls"}')
            yield ToolCallDelta(index=1, id="call_2", name="shell", arguments_chunk='{"command": "pwd"}')
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=0.2),
                finish_reason="tool_calls",
            )
        else:
            yield ContentDelta(text="Done")
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=20, completion_tokens=10, total_tokens=30, elapsed_seconds=0.2),
                finish_reason="stop",
            )

    async def track_permission(name, arguments):
        permission_order.append(arguments.get("command"))
        return True

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = []
    mock_registry.needs_permission.return_value = True
    mock_registry.execute = AsyncMock(return_value="output")

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "run both"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=track_permission,
        )

        events = []
        async for event in loop.run():
            events.append(event)

    assert permission_order == ["ls", "pwd"]


@pytest.mark.asyncio
async def test_agent_loop_malformed_json_arguments():
    """Malformed JSON arguments produce a clear error, not silent empty dict execution."""
    call_count = 0

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield ToolCallDelta(index=0, id="call_bad", name="read_file", arguments_chunk='{bad json!!!}')
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=5, completion_tokens=3, total_tokens=8, elapsed_seconds=0.1),
                finish_reason="tool_calls",
            )
        else:
            yield ContentDelta(text="I see the error")
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=0.1),
                finish_reason="stop",
            )

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = []
    mock_registry.needs_permission.return_value = False
    mock_registry.execute = AsyncMock(return_value="should not be called")

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "bad call"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=AsyncMock(return_value=True),
        )

        events = []
        async for event in loop.run():
            events.append(event)

    tool_results = [e for e in events if isinstance(e, ToolResult)]
    assert len(tool_results) == 1
    assert tool_results[0].is_error is True
    assert "read_file" in tool_results[0].output
    assert "JSON" in tool_results[0].output or "json" in tool_results[0].output.lower()

    mock_registry.execute.assert_not_called()


@pytest.mark.asyncio
async def test_agent_loop_retry_then_succeed():
    """Transient error retries once and succeeds on second attempt."""
    call_count = 0
    exec_count = 0

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield ToolCallDelta(index=0, id="call_retry", name="web_search", arguments_chunk='{"query": "test"}')
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=5, completion_tokens=3, total_tokens=8, elapsed_seconds=0.1),
                finish_reason="tool_calls",
            )
        else:
            yield ContentDelta(text="Got results")
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=0.1),
                finish_reason="stop",
            )

    async def flaky_execute(name, arguments):
        nonlocal exec_count
        exec_count += 1
        if exec_count == 1:
            return "Error: search request failed — network timeout"
        return "1. Result Title\n   https://example.com\n   A search result"

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = []
    mock_registry.needs_permission.return_value = False
    mock_registry.execute = AsyncMock(side_effect=flaky_execute)

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "search test"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=AsyncMock(return_value=True),
        )

        events = []
        async for event in loop.run():
            events.append(event)

    tool_results = [e for e in events if isinstance(e, ToolResult)]
    assert len(tool_results) == 1
    assert tool_results[0].is_error is False
    assert "Result Title" in tool_results[0].output
    assert exec_count == 2


@pytest.mark.asyncio
async def test_agent_loop_retry_then_fail():
    """Transient error retries once but still fails — structured error returned."""
    call_count = 0

    async def mock_stream(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield ToolCallDelta(index=0, id="call_fail", name="web_search", arguments_chunk='{"query": "test"}')
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=5, completion_tokens=3, total_tokens=8, elapsed_seconds=0.1),
                finish_reason="tool_calls",
            )
        else:
            yield ContentDelta(text="Search failed")
            yield StreamEnd(
                usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=0.1),
                finish_reason="stop",
            )

    mock_registry = MagicMock()
    mock_registry.get_tool_schemas.return_value = []
    mock_registry.needs_permission.return_value = False
    mock_registry.execute = AsyncMock(return_value="Error: connection timeout")

    with patch("core.agent.stream_completion", side_effect=mock_stream):
        loop = AgentLoop(
            model="test/model",
            messages=[{"role": "user", "content": "search test"}],
            system_prompt=None,
            tools=mock_registry,
            permission_fn=AsyncMock(return_value=True),
        )

        events = []
        async for event in loop.run():
            events.append(event)

    tool_results = [e for e in events if isinstance(e, ToolResult)]
    assert len(tool_results) == 1
    assert tool_results[0].is_error is True
    assert "web_search" in tool_results[0].output
    assert mock_registry.execute.await_count == 2
