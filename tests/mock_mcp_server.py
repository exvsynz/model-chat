"""Minimal MCP server for testing. Run via: python tests/mock_mcp_server.py"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test-server")


@mcp.tool()
def echo(message: str) -> str:
    """Echo a message back."""
    return f"echo: {message}"


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.tool()
def fail_tool() -> str:
    """A tool that always fails."""
    raise ValueError("intentional failure")


if __name__ == "__main__":
    mcp.run(transport="stdio")
