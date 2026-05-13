import asyncio
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_read_file_returns_contents(tmp_path):
    """read_file tool returns file contents with line numbers."""
    from core.tools import create_default_registry

    test_file = tmp_path / "hello.txt"
    test_file.write_text("line one\nline two\nline three\n")

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("read_file", {"path": "hello.txt"})

    assert "line one" in result
    assert "line two" in result
    assert "line three" in result


@pytest.mark.asyncio
async def test_read_file_with_offset_limit(tmp_path):
    """read_file respects offset and limit parameters."""
    from core.tools import create_default_registry

    lines = [f"line {i}" for i in range(1, 21)]
    test_file = tmp_path / "big.txt"
    test_file.write_text("\n".join(lines) + "\n")

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("read_file", {"path": "big.txt", "offset": 5, "limit": 3})

    assert "line 6" in result
    assert "line 7" in result
    assert "line 8" in result
    assert "line 1\t" not in result


@pytest.mark.asyncio
async def test_read_file_not_found(tmp_path):
    """read_file returns error for missing files."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("read_file", {"path": "nope.txt"})

    assert "error" in result.lower() or "not found" in result.lower()


@pytest.mark.asyncio
async def test_glob_finds_files(tmp_path):
    """glob tool finds files matching pattern."""
    from core.tools import create_default_registry

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("pass")
    (tmp_path / "src" / "util.py").write_text("pass")
    (tmp_path / "readme.md").write_text("hi")

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("glob", {"pattern": "**/*.py"})

    assert "main.py" in result
    assert "util.py" in result
    assert "readme.md" not in result


@pytest.mark.asyncio
async def test_glob_with_path(tmp_path):
    """glob tool respects path parameter."""
    from core.tools import create_default_registry

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("pass")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "helper.py").write_text("pass")

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("glob", {"pattern": "*.py", "path": "src"})

    assert "app.py" in result
    assert "helper.py" not in result


@pytest.mark.asyncio
async def test_grep_finds_matches(tmp_path):
    """grep tool finds regex matches in files."""
    from core.tools import create_default_registry

    (tmp_path / "code.py").write_text("def hello():\n    return 'world'\n\ndef goodbye():\n    pass\n")

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("grep", {"pattern": "def \\w+"})

    assert "hello" in result
    assert "goodbye" in result


@pytest.mark.asyncio
async def test_grep_with_include_filter(tmp_path):
    """grep tool filters by file glob."""
    from core.tools import create_default_registry

    (tmp_path / "code.py").write_text("TODO: fix this\n")
    (tmp_path / "notes.md").write_text("TODO: write docs\n")

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("grep", {"pattern": "TODO", "include": "*.py"})

    assert "code.py" in result
    assert "notes.md" not in result


@pytest.mark.asyncio
async def test_write_file_creates_file(tmp_path):
    """write_file creates a new file with content."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("write_file", {"path": "new.txt", "content": "hello world"})

    written = (tmp_path / "new.txt").read_text()
    assert written == "hello world"
    assert "wrote" in result.lower() or "bytes" in result.lower()


@pytest.mark.asyncio
async def test_write_file_creates_directories(tmp_path):
    """write_file creates parent directories if needed."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=tmp_path)
    await registry.execute("write_file", {"path": "src/deep/file.py", "content": "pass"})

    assert (tmp_path / "src" / "deep" / "file.py").read_text() == "pass"


@pytest.mark.asyncio
async def test_write_file_blocks_path_escape(tmp_path):
    """write_file refuses to write outside work_dir."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("write_file", {"path": "../../etc/evil.txt", "content": "bad"})

    assert "denied" in result.lower() or "outside" in result.lower()


@pytest.mark.asyncio
async def test_edit_file_replaces_string(tmp_path):
    """edit_file replaces an exact unique match."""
    from core.tools import create_default_registry

    test_file = tmp_path / "code.py"
    test_file.write_text("def hello():\n    return 'world'\n")

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("edit_file", {
        "path": "code.py",
        "old_string": "return 'world'",
        "new_string": "return 'universe'",
    })

    assert "replaced" in result.lower()
    assert "return 'universe'" in test_file.read_text()
    assert "return 'world'" not in test_file.read_text()


@pytest.mark.asyncio
async def test_edit_file_not_found(tmp_path):
    """edit_file returns error when old_string is not in file."""
    from core.tools import create_default_registry

    test_file = tmp_path / "code.py"
    test_file.write_text("def hello():\n    pass\n")

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("edit_file", {
        "path": "code.py",
        "old_string": "nonexistent string",
        "new_string": "replacement",
    })

    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_edit_file_ambiguous_match(tmp_path):
    """edit_file rejects when old_string matches multiple locations."""
    from core.tools import create_default_registry

    test_file = tmp_path / "code.py"
    test_file.write_text("pass\npass\npass\n")

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("edit_file", {
        "path": "code.py",
        "old_string": "pass",
        "new_string": "return",
    })

    assert "3 locations" in result
    assert test_file.read_text() == "pass\npass\npass\n"


@pytest.mark.asyncio
async def test_edit_file_blocks_path_escape(tmp_path):
    """edit_file refuses to edit outside work_dir."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("edit_file", {
        "path": "../../etc/passwd",
        "old_string": "root",
        "new_string": "hacked",
    })

    assert "denied" in result.lower() or "outside" in result.lower()


@pytest.mark.asyncio
async def test_edit_file_missing_file(tmp_path):
    """edit_file returns error for nonexistent file."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("edit_file", {
        "path": "nope.py",
        "old_string": "x",
        "new_string": "y",
    })

    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_shell_runs_command(tmp_path):
    """shell tool runs a command and returns output."""
    import sys
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=tmp_path)
    cmd = 'Write-Output "hello world"' if sys.platform == "win32" else "echo hello world"
    result = await registry.execute("shell", {"command": cmd})

    assert "hello world" in result


@pytest.mark.asyncio
async def test_shell_returns_exit_code_on_failure(tmp_path):
    """shell tool includes exit code on non-zero exit."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("shell", {"command": "exit 1"})

    assert "exit code" in result.lower() or "1" in result


def test_registry_generates_openai_schemas():
    """ToolRegistry produces valid OpenAI tool schemas."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=Path("."))
    schemas = registry.get_tool_schemas()

    assert len(schemas) == 7
    names = {s["function"]["name"] for s in schemas}
    assert names == {"read_file", "write_file", "edit_file", "shell", "glob", "grep", "web_search"}

    for schema in schemas:
        assert schema["type"] == "function"
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]


@pytest.mark.asyncio
async def test_web_search_missing_api_key():
    """web_search returns error when BRAVE_SEARCH_API_KEY is not set."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=Path("."))
    with patch.dict(os.environ, {}, clear=True):
        result = await registry.execute("web_search", {"query": "test"})
    assert "BRAVE_SEARCH_API_KEY" in result


@pytest.mark.asyncio
async def test_web_search_returns_results():
    """web_search parses Brave API response into formatted results."""
    from core.tools import create_default_registry

    mock_response = {
        "web": {
            "results": [
                {"title": "Result One", "url": "https://example.com/1", "description": "First result snippet"},
                {"title": "Result Two", "url": "https://example.com/2", "description": "Second result snippet"},
            ]
        }
    }

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: mock_response
    mock_resp.raise_for_status = lambda: None

    registry = create_default_registry(work_dir=Path("."))
    with patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"}):
        with patch("core.tools.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await registry.execute("web_search", {"query": "test query"})

    assert "Result One" in result
    assert "https://example.com/1" in result
    assert "Result Two" in result
    assert "First result snippet" in result


@pytest.mark.asyncio
async def test_web_search_no_results():
    """web_search handles empty results gracefully."""
    from core.tools import create_default_registry

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {"web": {"results": []}}
    mock_resp.raise_for_status = lambda: None

    registry = create_default_registry(work_dir=Path("."))
    with patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"}):
        with patch("core.tools.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await registry.execute("web_search", {"query": "nonexistent"})

    assert result == "No results found"


@pytest.mark.asyncio
async def test_web_search_http_error():
    """web_search handles HTTP errors from Brave API."""
    from core.tools import create_default_registry
    import httpx

    registry = create_default_registry(work_dir=Path("."))

    mock_resp = AsyncMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status = lambda: (_ for _ in ()).throw(
        httpx.HTTPStatusError("rate limited", request=AsyncMock(), response=mock_resp)
    )

    with patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"}):
        with patch("core.tools.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await registry.execute("web_search", {"query": "test"})

    assert "429" in result


@pytest.mark.asyncio
async def test_web_search_network_error():
    """web_search handles network failures gracefully."""
    from core.tools import create_default_registry
    import httpx

    registry = create_default_registry(work_dir=Path("."))

    with patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"}):
        with patch("core.tools.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await registry.execute("web_search", {"query": "test"})

    assert "Error" in result
    assert "failed" in result


@pytest.mark.asyncio
async def test_web_search_respects_count_param():
    """web_search passes count parameter and caps at 10."""
    from core.tools import create_default_registry

    mock_response = {
        "web": {
            "results": [
                {"title": f"Result {i}", "url": f"https://example.com/{i}", "description": f"Snippet {i}"}
                for i in range(3)
            ]
        }
    }

    mock_resp = AsyncMock()
    mock_resp.json = lambda: mock_response
    mock_resp.raise_for_status = lambda: None

    registry = create_default_registry(work_dir=Path("."))
    with patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"}):
        with patch("core.tools.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await registry.execute("web_search", {"query": "test", "count": 3})

            call_args = mock_client.get.call_args
            assert call_args[1]["params"]["count"] == 3

    assert "Result 0" in result
    assert "Result 2" in result
