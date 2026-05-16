from __future__ import annotations

import logging

from core.mcp_adapter import register_mcp_tools
from core.mcp_client import MCPClient, MCPError, MCPServerConfig
from core.tools import ToolRegistry

logger = logging.getLogger("model-chat.mcp")


class MCPManager:
    """Manages lifecycle of MCP server connections."""

    def __init__(self):
        self.clients: list[MCPClient] = []

    async def connect_all(self, configs: list[MCPServerConfig]) -> None:
        for config in configs:
            client = MCPClient(config)
            try:
                await client.connect()
                self.clients.append(client)
                logger.info("MCP server '%s': connected", config.name)
            except MCPError as e:
                logger.warning("MCP server '%s' failed to connect: %s", config.name, e)

    async def register_tools(self, registry: ToolRegistry) -> None:
        for client in self.clients:
            await register_mcp_tools(registry, client)

    async def setup(self, registry: ToolRegistry, configs: list[MCPServerConfig]) -> None:
        await self.connect_all(configs)
        await self.register_tools(registry)

    async def shutdown(self) -> None:
        for client in self.clients:
            try:
                await client.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting '%s': %s", client.config.name, e)
        self.clients.clear()
