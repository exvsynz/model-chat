import asyncio
import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

import httpx


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    execute: Callable[[dict], Awaitable[str]]
    permission: str  # "auto" or "prompt"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def needs_permission(self, name: str) -> bool:
        tool = self._tools.get(name)
        return tool.permission == "prompt" if tool else True

    async def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'"
        try:
            return await tool.execute(arguments)
        except Exception as e:
            return f"Error: {e}"

    def get_tool_schemas(self) -> list[dict]:
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas


def create_default_registry(work_dir: Path) -> ToolRegistry:
    registry = ToolRegistry()

    async def read_file(args: dict) -> str:
        path = work_dir / args["path"]
        if not path.exists():
            return f"Error: file not found: {args['path']}"
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error reading file: {e}"
        lines = content.splitlines()
        offset = args.get("offset", 0)
        limit = args.get("limit", len(lines))
        selected = lines[offset:offset + limit]
        numbered = [f"{offset + i + 1}\t{line}" for i, line in enumerate(selected)]
        return "\n".join(numbered)

    registry.register(Tool(
        name="read_file",
        description="Read a file's contents. Returns lines with line numbers.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to working directory"},
                "offset": {"type": "integer", "description": "Line offset to start from (0-based)"},
                "limit": {"type": "integer", "description": "Maximum number of lines to return"},
            },
            "required": ["path"],
        },
        execute=read_file,
        permission="auto",
    ))

    async def glob_tool(args: dict) -> str:
        pattern = args["pattern"]
        base = work_dir / args.get("path", "")
        if not base.exists():
            return f"Error: directory not found: {args.get('path', '')}"
        matches = sorted(base.rglob(pattern) if "**" in pattern else base.glob(pattern))
        if not matches:
            return "No files found"
        rel_paths = []
        for m in matches[:100]:
            try:
                rel_paths.append(str(m.relative_to(work_dir)))
            except ValueError:
                rel_paths.append(str(m))
        result = "\n".join(rel_paths)
        if len(matches) > 100:
            result += f"\n... ({len(matches)} total, showing first 100)"
        return result

    registry.register(Tool(
        name="glob",
        description="Find files matching a glob pattern. Returns matching paths.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py', 'src/*.ts')"},
                "path": {"type": "string", "description": "Base directory to search from (relative to working directory)"},
            },
            "required": ["pattern"],
        },
        execute=glob_tool,
        permission="auto",
    ))

    async def grep_tool(args: dict) -> str:
        pattern = args["pattern"]
        base = work_dir / args.get("path", "")
        include = args.get("include", "")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Error: invalid regex: {e}"

        matches = []
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if include and not fnmatch.fnmatch(fname, include):
                    continue
                fpath = Path(root) / fname
                try:
                    text = fpath.read_text(encoding="utf-8", errors="replace")
                except (OSError, UnicodeDecodeError):
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        rel = fpath.relative_to(work_dir)
                        matches.append(f"{rel}:{i}: {line.rstrip()}")
                        if len(matches) >= 50:
                            break
                if len(matches) >= 50:
                    break
            if len(matches) >= 50:
                break

        if not matches:
            return "No matches found"
        result = "\n".join(matches[:20])
        if len(matches) > 20:
            result += f"\n... {len(matches) - 20} more matches"
        return result

    registry.register(Tool(
        name="grep",
        description="Search file contents with a regex pattern. Returns matching lines with file:line format.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regular expression pattern to search for"},
                "path": {"type": "string", "description": "Directory to search in (relative to working directory)"},
                "include": {"type": "string", "description": "File glob filter (e.g. '*.py', '*.ts')"},
            },
            "required": ["pattern"],
        },
        execute=grep_tool,
        permission="auto",
    ))

    async def write_file(args: dict) -> str:
        rel_path = Path(args["path"])
        target = (work_dir / rel_path).resolve()
        try:
            target.relative_to(work_dir.resolve())
        except ValueError:
            return "Error: write denied — path resolves outside working directory"
        target.parent.mkdir(parents=True, exist_ok=True)
        content = args["content"]
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content.encode('utf-8'))} bytes to {args['path']}"

    registry.register(Tool(
        name="write_file",
        description="Write content to a file. Creates parent directories if needed. Overwrites existing files.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to working directory"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
        },
        execute=write_file,
        permission="prompt",
    ))

    async def bash_tool(args: dict) -> str:
        command = args["command"]
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=work_dir,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            output = stdout.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                output += f"\n[exit code: {proc.returncode}]"
            return output if output.strip() else "(no output)"
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return "Error: command timed out after 120 seconds"
        except Exception as e:
            return f"Error running command: {e}"

    registry.register(Tool(
        name="bash",
        description="Run a shell command and return its output (stdout + stderr combined).",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
            },
            "required": ["command"],
        },
        execute=bash_tool,
        permission="prompt",
    ))

    async def web_search(args: dict) -> str:
        api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return "Error: BRAVE_SEARCH_API_KEY environment variable not set"
        query = args["query"]
        count = min(args.get("count", 5), 10)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": count},
                    headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                    timeout=15,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return f"Error: Brave Search API returned {e.response.status_code}"
        except httpx.RequestError as e:
            return f"Error: search request failed — {e}"

        data = resp.json()
        results = data.get("web", {}).get("results", [])
        if not results:
            return "No results found"

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("description", "")
            lines.append(f"{i}. {title}\n   {url}\n   {snippet}")
        return "\n\n".join(lines)

    registry.register(Tool(
        name="web_search",
        description="Search the web using Brave Search. Use this when you need current or up-to-date information.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "count": {"type": "integer", "description": "Number of results (1-10, default 5)"},
            },
            "required": ["query"],
        },
        execute=web_search,
        permission="auto",
    ))

    return registry
