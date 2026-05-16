from __future__ import annotations

import logging
import re

from core.mcp_client import MCPClient, MCPError
from core.tools import Tool, ToolRegistry

logger = logging.getLogger("model-chat.mcp")


def _sanitize_name(server_name: str, tool_name: str) -> str:
    raw = f"mcp_{server_name}_{tool_name}"
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)


def mcp_tool_to_native(mcp_tool, client: MCPClient) -> Tool:
    original_name = mcp_tool.name
    namespaced = _sanitize_name(client.config.name, original_name)

    async def execute(arguments: dict) -> str:
        try:
            text, is_error = await client.call_tool(original_name, arguments)
        except MCPError as e:
            return f"Error: {e}"
        if is_error:
            return f"Error (MCP): {text}"
        return text

    return Tool(
        name=namespaced,
        description=mcp_tool.description or "",
        parameters=mcp_tool.inputSchema or {"type": "object", "properties": {}},
        execute=execute,
        permission="prompt",
    )


async def register_mcp_tools(registry: ToolRegistry, client: MCPClient) -> None:
    mcp_tools = await client.list_tools()
    for mcp_tool in mcp_tools:
        tool = mcp_tool_to_native(mcp_tool, client)
        registry.register(tool)
        logger.debug("Registered MCP tool: %s", tool.name)
