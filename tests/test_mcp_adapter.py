from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp import types as mcp_types

from core.mcp_adapter import mcp_tool_to_native, register_mcp_tools
from core.mcp_client import MCPClient, MCPError, MCPServerConfig
from core.tools import ToolRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mcp_tool(name="echo", description="Echo a message", input_schema=None):
    tool = MagicMock(spec=mcp_types.Tool)
    tool.name = name
    tool.description = description
    tool.inputSchema = input_schema or {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }
    return tool


def _make_client(server_name="filesystem"):
    config = MCPServerConfig(name=server_name, command="python", args=["-m", "server"])
    client = MCPClient(config)
    client._session = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Tests: mcp_tool_to_native
# ---------------------------------------------------------------------------


class TestMcpToolToNative:
    def test_name_is_namespaced(self):
        mcp_tool = _make_mcp_tool(name="read_file")
        client = _make_client(server_name="filesystem")
        tool = mcp_tool_to_native(mcp_tool, client)
        assert tool.name == "mcp_filesystem_read_file"

    def test_description_passed_through(self):
        mcp_tool = _make_mcp_tool(description="Read a file from disk")
        client = _make_client()
        tool = mcp_tool_to_native(mcp_tool, client)
        assert tool.description == "Read a file from disk"

    def test_parameters_passed_through(self):
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        mcp_tool = _make_mcp_tool(input_schema=schema)
        client = _make_client()
        tool = mcp_tool_to_native(mcp_tool, client)
        assert tool.parameters == schema

    def test_permission_is_prompt(self):
        mcp_tool = _make_mcp_tool()
        client = _make_client()
        tool = mcp_tool_to_native(mcp_tool, client)
        assert tool.permission == "prompt"

    @pytest.mark.asyncio
    async def test_execute_calls_client(self):
        mcp_tool = _make_mcp_tool(name="echo")
        client = _make_client(server_name="test")
        client.call_tool = AsyncMock(return_value=("echo: hello", False))

        tool = mcp_tool_to_native(mcp_tool, client)
        result = await tool.execute({"message": "hello"})
        assert result == "echo: hello"
        client.call_tool.assert_awaited_once_with("echo", {"message": "hello"})

    @pytest.mark.asyncio
    async def test_execute_returns_error_text_on_tool_error(self):
        mcp_tool = _make_mcp_tool(name="fail")
        client = _make_client(server_name="test")
        client.call_tool = AsyncMock(return_value=("something went wrong", True))

        tool = mcp_tool_to_native(mcp_tool, client)
        result = await tool.execute({})
        assert "something went wrong" in result

    @pytest.mark.asyncio
    async def test_execute_wraps_mcp_error(self):
        mcp_tool = _make_mcp_tool(name="broken")
        client = _make_client(server_name="test")
        client.call_tool = AsyncMock(side_effect=MCPError("connection lost"))

        tool = mcp_tool_to_native(mcp_tool, client)
        result = await tool.execute({})
        assert "connection lost" in result

    def test_name_sanitizes_special_chars(self):
        mcp_tool = _make_mcp_tool(name="read-file.v2")
        client = _make_client(server_name="my-server")
        tool = mcp_tool_to_native(mcp_tool, client)
        # Should only contain alphanumeric and underscores
        assert tool.name == "mcp_my_server_read_file_v2"


# ---------------------------------------------------------------------------
# Tests: register_mcp_tools
# ---------------------------------------------------------------------------


class TestRegisterMcpTools:
    @pytest.mark.asyncio
    async def test_registers_all_tools(self):
        client = _make_client(server_name="fs")
        tools = [_make_mcp_tool(name="read"), _make_mcp_tool(name="write")]
        client.list_tools = AsyncMock(return_value=tools)

        registry = ToolRegistry()
        await register_mcp_tools(registry, client)

        assert registry.get("mcp_fs_read") is not None
        assert registry.get("mcp_fs_write") is not None

    @pytest.mark.asyncio
    async def test_tools_appear_in_schemas(self):
        client = _make_client(server_name="db")
        tools = [_make_mcp_tool(name="query", description="Run a query")]
        client.list_tools = AsyncMock(return_value=tools)

        registry = ToolRegistry()
        await register_mcp_tools(registry, client)

        schemas = registry.get_tool_schemas()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "mcp_db_query"
        assert schemas[0]["function"]["description"] == "Run a query"

    @pytest.mark.asyncio
    async def test_does_not_clobber_existing_tools(self):
        client = _make_client(server_name="ext")
        tools = [_make_mcp_tool(name="echo")]
        client.list_tools = AsyncMock(return_value=tools)

        registry = ToolRegistry()
        # Pre-register a native tool
        from core.tools import Tool

        native = Tool(
            name="native_tool",
            description="A native tool",
            parameters={"type": "object", "properties": {}},
            execute=AsyncMock(return_value="ok"),
            permission="auto",
        )
        registry.register(native)

        await register_mcp_tools(registry, client)

        assert registry.get("native_tool") is not None
        assert registry.get("mcp_ext_echo") is not None
        assert len(registry.get_tool_schemas()) == 2

    @pytest.mark.asyncio
    async def test_handles_empty_tool_list(self):
        client = _make_client(server_name="empty")
        client.list_tools = AsyncMock(return_value=[])

        registry = ToolRegistry()
        await register_mcp_tools(registry, client)

        assert registry.get_tool_schemas() == []

    @pytest.mark.asyncio
    async def test_execution_routes_through_client(self):
        client = _make_client(server_name="srv")
        tools = [_make_mcp_tool(name="ping")]
        client.list_tools = AsyncMock(return_value=tools)
        client.call_tool = AsyncMock(return_value=("pong", False))

        registry = ToolRegistry()
        await register_mcp_tools(registry, client)

        result = await registry.execute("mcp_srv_ping", {"host": "localhost"})
        assert "pong" in result
        client.call_tool.assert_awaited_once_with("ping", {"host": "localhost"})
