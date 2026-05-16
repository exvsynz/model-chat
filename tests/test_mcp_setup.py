from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.mcp_client import MCPError, MCPServerConfig
from core.mcp_setup import MCPManager
from core.tools import ToolRegistry


def _make_config(name="test-server", enabled=True):
    return MCPServerConfig(name=name, command="python", args=["-m", "server"], enabled=enabled)


# ---------------------------------------------------------------------------
# Tests: MCPManager
# ---------------------------------------------------------------------------


class TestMCPManager:
    @pytest.mark.asyncio
    async def test_setup_connects_and_registers_tools(self):
        config = _make_config(name="fs")
        mock_tool = MagicMock()
        mock_tool.name = "read"
        mock_tool.description = "Read a file"
        mock_tool.inputSchema = {"type": "object", "properties": {}}

        with patch("core.mcp_setup.MCPClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.config = config
            client_instance.list_tools = AsyncMock(return_value=[mock_tool])
            client_instance.connected = True
            MockClient.return_value = client_instance

            registry = ToolRegistry()
            manager = MCPManager()
            await manager.setup(registry, [config])

            client_instance.connect.assert_awaited_once()
            assert registry.get("mcp_fs_read") is not None
            assert len(manager.clients) == 1

    @pytest.mark.asyncio
    async def test_setup_skips_failed_connection(self):
        config = _make_config(name="broken")

        with patch("core.mcp_setup.MCPClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.config = config
            client_instance.connect = AsyncMock(side_effect=MCPError("process not found"))
            client_instance.connected = False
            MockClient.return_value = client_instance

            registry = ToolRegistry()
            manager = MCPManager()
            await manager.setup(registry, [config])

            assert len(manager.clients) == 0
            assert registry.get_tool_schemas() == []

    @pytest.mark.asyncio
    async def test_setup_multiple_servers(self):
        configs = [_make_config(name="a"), _make_config(name="b")]

        with patch("core.mcp_setup.MCPClient") as MockClient:
            mock_tool_a = MagicMock()
            mock_tool_a.name = "tool_a"
            mock_tool_a.description = "Tool A"
            mock_tool_a.inputSchema = {"type": "object", "properties": {}}

            mock_tool_b = MagicMock()
            mock_tool_b.name = "tool_b"
            mock_tool_b.description = "Tool B"
            mock_tool_b.inputSchema = {"type": "object", "properties": {}}

            def make_client(cfg):
                client = AsyncMock()
                client.config = cfg
                client.connected = True
                if cfg.name == "a":
                    client.list_tools = AsyncMock(return_value=[mock_tool_a])
                else:
                    client.list_tools = AsyncMock(return_value=[mock_tool_b])
                return client

            MockClient.side_effect = make_client

            registry = ToolRegistry()
            manager = MCPManager()
            await manager.setup(registry, configs)

            assert len(manager.clients) == 2
            assert registry.get("mcp_a_tool_a") is not None
            assert registry.get("mcp_b_tool_b") is not None

    @pytest.mark.asyncio
    async def test_shutdown_disconnects_all(self):
        config = _make_config(name="srv")

        with patch("core.mcp_setup.MCPClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.config = config
            client_instance.list_tools = AsyncMock(return_value=[])
            client_instance.connected = True
            MockClient.return_value = client_instance

            registry = ToolRegistry()
            manager = MCPManager()
            await manager.setup(registry, [config])
            await manager.shutdown()

            client_instance.disconnect.assert_awaited_once()
            assert len(manager.clients) == 0

    @pytest.mark.asyncio
    async def test_setup_with_empty_configs(self):
        registry = ToolRegistry()
        manager = MCPManager()
        await manager.setup(registry, [])

        assert len(manager.clients) == 0
        assert registry.get_tool_schemas() == []

    @pytest.mark.asyncio
    async def test_shutdown_when_no_clients(self):
        manager = MCPManager()
        await manager.shutdown()  # should not raise

    @pytest.mark.asyncio
    async def test_partial_failure_still_connects_others(self):
        configs = [_make_config(name="good"), _make_config(name="bad")]

        with patch("core.mcp_setup.MCPClient") as MockClient:
            mock_tool = MagicMock()
            mock_tool.name = "ping"
            mock_tool.description = "Ping"
            mock_tool.inputSchema = {"type": "object", "properties": {}}

            def make_client(cfg):
                client = AsyncMock()
                client.config = cfg
                if cfg.name == "bad":
                    client.connect = AsyncMock(side_effect=MCPError("fail"))
                    client.connected = False
                else:
                    client.connected = True
                    client.list_tools = AsyncMock(return_value=[mock_tool])
                return client

            MockClient.side_effect = make_client

            registry = ToolRegistry()
            manager = MCPManager()
            await manager.setup(registry, configs)

            assert len(manager.clients) == 1
            assert registry.get("mcp_good_ping") is not None
