"""End-to-end integration tests for MCP support.

These tests spawn a real MCP server subprocess (tests/mock_mcp_server.py)
and validate the full pipeline: connect → list tools → call tool → disconnect.
"""

import sys
from pathlib import Path

import pytest

from core.mcp_adapter import register_mcp_tools
from core.mcp_client import MCPClient, MCPError, MCPServerConfig
from core.mcp_config import load_mcp_config
from core.mcp_setup import MCPManager
from core.tools import ToolRegistry

MOCK_SERVER = str(Path(__file__).parent / "mock_mcp_server.py")


def _server_config(name="test-server"):
    return MCPServerConfig(
        name=name,
        command=sys.executable,
        args=[MOCK_SERVER],
    )


# ---------------------------------------------------------------------------
# Tests: full lifecycle with real subprocess
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_list_tools_disconnect():
    """Connect to mock server, list tools, then disconnect."""
    client = MCPClient(_server_config())
    await client.connect()
    assert client.connected

    tools = await client.list_tools()
    tool_names = [t.name for t in tools]
    assert "echo" in tool_names
    assert "add" in tool_names
    assert "fail_tool" in tool_names

    await client.disconnect()
    assert not client.connected


@pytest.mark.asyncio
async def test_call_tool_echo():
    """Call the echo tool and verify the response."""
    async with MCPClient(_server_config()) as client:
        text, is_error = await client.call_tool("echo", {"message": "hello world"})
        assert is_error is False
        assert "hello world" in text


@pytest.mark.asyncio
async def test_call_tool_add():
    """Call the add tool and verify arithmetic."""
    async with MCPClient(_server_config()) as client:
        text, is_error = await client.call_tool("add", {"a": 3, "b": 7})
        assert is_error is False
        assert "10" in text


@pytest.mark.asyncio
async def test_call_tool_error():
    """Call a tool that raises an error and verify is_error flag."""
    async with MCPClient(_server_config()) as client:
        text, is_error = await client.call_tool("fail_tool", {})
        assert is_error is True
        assert "intentional failure" in text.lower() or "error" in text.lower()


@pytest.mark.asyncio
async def test_adapter_registers_tools_from_real_server():
    """Verify adapter correctly bridges real MCP tools into ToolRegistry."""
    registry = ToolRegistry()
    async with MCPClient(_server_config(name="mock")) as client:
        await register_mcp_tools(registry, client)

        schemas = registry.get_tool_schemas()
        schema_names = [s["function"]["name"] for s in schemas]
        assert "mcp_mock_echo" in schema_names
        assert "mcp_mock_add" in schema_names

        result = await registry.execute("mcp_mock_echo", {"message": "integration"})
        assert "integration" in result


@pytest.mark.asyncio
async def test_manager_full_lifecycle():
    """MCPManager connects, registers tools, and shuts down cleanly."""
    registry = ToolRegistry()
    manager = MCPManager()
    await manager.setup(registry, [_server_config(name="e2e")])

    assert len(manager.clients) == 1
    assert registry.get("mcp_e2e_echo") is not None

    result = await registry.execute("mcp_e2e_add", {"a": 5, "b": 3})
    assert "8" in result

    await manager.shutdown()
    assert len(manager.clients) == 0


@pytest.mark.asyncio
async def test_invalid_server_command():
    """Non-existent command fails gracefully."""
    config = MCPServerConfig(
        name="nonexistent",
        command="this_command_does_not_exist_xyz",
        args=[],
    )
    client = MCPClient(config)
    with pytest.raises(MCPError, match="Failed to connect"):
        await client.connect()
    assert not client.connected


@pytest.mark.asyncio
async def test_manager_skips_bad_server():
    """Manager continues if one server fails to connect."""
    good = _server_config(name="good")
    bad = MCPServerConfig(name="bad", command="nonexistent_cmd_xyz", args=[])

    registry = ToolRegistry()
    manager = MCPManager()
    await manager.setup(registry, [bad, good])

    assert len(manager.clients) == 1
    assert registry.get("mcp_good_echo") is not None

    await manager.shutdown()


@pytest.mark.asyncio
async def test_config_to_connection():
    """Load config from YAML file, connect, and call a tool."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(f"""
servers:
  testmock:
    command: "{sys.executable.replace(chr(92), "/")}"
    args: ["{MOCK_SERVER.replace(chr(92), "/")}"]
    enabled: true
""")
        cfg_path = Path(f.name)

    try:
        configs = load_mcp_config(cfg_path)
        assert len(configs) == 1
        assert configs[0].name == "testmock"

        registry = ToolRegistry()
        manager = MCPManager()
        await manager.setup(registry, configs)

        assert registry.get("mcp_testmock_echo") is not None
        result = await registry.execute("mcp_testmock_echo", {"message": "yaml-test"})
        assert "yaml-test" in result

        await manager.shutdown()
    finally:
        cfg_path.unlink(missing_ok=True)
