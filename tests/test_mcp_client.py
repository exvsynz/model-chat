from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types as mcp_types

from core.mcp_client import MCPClient, MCPError, MCPServerConfig, _extract_text

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides):
    defaults = {"name": "test", "command": "python", "args": ["-m", "mock_server"]}
    defaults.update(overrides)
    return MCPServerConfig(**defaults)


class _AsyncCM:
    """Minimal async context manager that yields a fixed value."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *a):
        pass


def _patch_mcp(mock_session):
    """Patch stdio_client and ClientSession to yield mock_session."""
    read, write = MagicMock(), MagicMock()
    return (
        patch("core.mcp_client.stdio_client", return_value=_AsyncCM((read, write))),
        patch("core.mcp_client.ClientSession", return_value=_AsyncCM(mock_session)),
    )


def _default_session():
    """Create a mock session with echo tool and call_tool response."""
    session = AsyncMock()
    session.initialize = AsyncMock()

    mock_tool = MagicMock()
    mock_tool.name = "echo"
    mock_tool.description = "Echo a message"
    mock_tool.inputSchema = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }

    tools_result = MagicMock()
    tools_result.tools = [mock_tool]
    session.list_tools = AsyncMock(return_value=tools_result)

    call_result = MagicMock()
    call_result.content = [mcp_types.TextContent(type="text", text="echo: hello")]
    call_result.isError = False
    session.call_tool = AsyncMock(return_value=call_result)

    return session


# ---------------------------------------------------------------------------
# Tests: connect / disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_initializes_session():
    session = _default_session()
    p1, p2 = _patch_mcp(session)
    with p1, p2:
        client = MCPClient(_make_config())
        assert not client.connected
        await client.connect()
        assert client.connected
        session.initialize.assert_awaited_once()
        await client.disconnect()
        assert not client.connected


@pytest.mark.asyncio
async def test_connect_is_idempotent():
    session = _default_session()
    p1, p2 = _patch_mcp(session)
    with p1, p2:
        client = MCPClient(_make_config())
        await client.connect()
        await client.connect()  # second call should be a no-op
        session.initialize.assert_awaited_once()
        await client.disconnect()


@pytest.mark.asyncio
async def test_connect_failure_raises_mcp_error():
    session = AsyncMock()
    session.initialize = AsyncMock(side_effect=OSError("process not found"))
    p1, p2 = _patch_mcp(session)
    with p1, p2:
        client = MCPClient(_make_config())
        with pytest.raises(MCPError, match="Failed to connect"):
            await client.connect()
        assert not client.connected


@pytest.mark.asyncio
async def test_disconnect_when_not_connected():
    client = MCPClient(_make_config())
    await client.disconnect()  # should not raise


# ---------------------------------------------------------------------------
# Tests: list_tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tools_returns_tools():
    session = _default_session()
    p1, p2 = _patch_mcp(session)
    with p1, p2:
        client = MCPClient(_make_config())
        await client.connect()
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "echo"
        await client.disconnect()


@pytest.mark.asyncio
async def test_list_tools_not_connected():
    client = MCPClient(_make_config())
    with pytest.raises(MCPError, match="Not connected"):
        await client.list_tools()


# ---------------------------------------------------------------------------
# Tests: call_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_tool_text_result():
    session = _default_session()
    p1, p2 = _patch_mcp(session)
    with p1, p2:
        client = MCPClient(_make_config())
        await client.connect()
        text, is_error = await client.call_tool("echo", {"message": "hello"})
        assert text == "echo: hello"
        assert is_error is False
        session.call_tool.assert_awaited_once_with("echo", arguments={"message": "hello"})
        await client.disconnect()


@pytest.mark.asyncio
async def test_call_tool_error_result():
    session = _default_session()
    error_result = MagicMock()
    error_result.content = [mcp_types.TextContent(type="text", text="tool failed")]
    error_result.isError = True
    session.call_tool = AsyncMock(return_value=error_result)

    p1, p2 = _patch_mcp(session)
    with p1, p2:
        client = MCPClient(_make_config())
        await client.connect()
        text, is_error = await client.call_tool("fail", {})
        assert text == "tool failed"
        assert is_error is True
        await client.disconnect()


@pytest.mark.asyncio
async def test_call_tool_not_connected():
    client = MCPClient(_make_config())
    with pytest.raises(MCPError, match="Not connected"):
        await client.call_tool("echo", {})


# ---------------------------------------------------------------------------
# Tests: async context manager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_manager():
    session = _default_session()
    p1, p2 = _patch_mcp(session)
    with p1, p2:
        async with MCPClient(_make_config()) as client:
            assert client.connected
            tools = await client.list_tools()
            assert len(tools) == 1
        assert not client.connected


# ---------------------------------------------------------------------------
# Tests: _extract_text
# ---------------------------------------------------------------------------


def test_extract_text_single_text():
    result = MagicMock()
    result.content = [mcp_types.TextContent(type="text", text="hello")]
    assert _extract_text(result) == "hello"


def test_extract_text_multiple_blocks():
    result = MagicMock()
    result.content = [
        mcp_types.TextContent(type="text", text="line 1"),
        mcp_types.TextContent(type="text", text="line 2"),
    ]
    assert _extract_text(result) == "line 1\nline 2"


def test_extract_text_image_block():
    result = MagicMock()
    result.content = [mcp_types.ImageContent(type="image", data="abc", mimeType="image/png")]
    assert _extract_text(result) == "[image: image/png]"


def test_extract_text_empty():
    result = MagicMock()
    result.content = []
    assert _extract_text(result) == ""


def test_extract_text_embedded_resource():
    resource = mcp_types.TextResourceContents(uri="file:///test.txt", text="config data")
    block = mcp_types.EmbeddedResource(type="resource", resource=resource)
    result = MagicMock()
    result.content = [block]
    assert _extract_text(result) == "config data"
