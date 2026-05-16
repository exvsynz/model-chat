from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from mcp import ClientSession, types
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger("model-chat.mcp")


class MCPError(Exception):
    pass


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    enabled: bool = True


class MCPClient:
    """Connects to an MCP server via stdio and exposes tool operations."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None

    @property
    def connected(self) -> bool:
        return self._session is not None

    async def connect(self) -> None:
        if self._session is not None:
            return

        self._exit_stack = AsyncExitStack()
        try:
            params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env,
            )
            read, write = await self._exit_stack.enter_async_context(stdio_client(params))
            session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._session = session
            logger.info("Connected to MCP server '%s'", self.config.name)
        except Exception as e:
            if self._exit_stack:
                await self._exit_stack.aclose()
                self._exit_stack = None
            raise MCPError(f"Failed to connect to '{self.config.name}': {e}") from e

    async def list_tools(self) -> list[types.Tool]:
        if not self._session:
            raise MCPError("Not connected")
        result = await self._session.list_tools()
        return list(result.tools)

    async def call_tool(self, name: str, arguments: dict) -> tuple[str, bool]:
        """Call a tool. Returns (result_text, is_error)."""
        if not self._session:
            raise MCPError("Not connected")
        result = await self._session.call_tool(name, arguments=arguments)
        text = _extract_text(result)
        return text, bool(result.isError)

    async def disconnect(self) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self._session = None
        logger.info("Disconnected from MCP server '%s'", self.config.name)

    async def __aenter__(self) -> MCPClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.disconnect()


def _extract_text(result) -> str:
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, types.TextContent):
            parts.append(block.text)
        elif isinstance(block, types.ImageContent):
            parts.append(f"[image: {block.mimeType}]")
        elif isinstance(block, types.EmbeddedResource):
            resource = block.resource
            if hasattr(resource, "text"):
                parts.append(resource.text)
            else:
                parts.append("[binary resource]")
        else:
            parts.append(str(block))
    return "\n".join(parts) if parts else ""
