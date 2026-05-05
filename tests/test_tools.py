import asyncio
import os
import pytest
from pathlib import Path
from unittest.mock import patch


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
async def test_bash_runs_command(tmp_path):
    """bash tool runs a command and returns output."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("bash", {"command": "echo hello world"})

    assert "hello world" in result


@pytest.mark.asyncio
async def test_bash_returns_exit_code_on_failure(tmp_path):
    """bash tool includes exit code on non-zero exit."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=tmp_path)
    result = await registry.execute("bash", {"command": "exit 1"})

    assert "exit code" in result.lower() or "1" in result


def test_registry_generates_openai_schemas():
    """ToolRegistry produces valid OpenAI tool schemas."""
    from core.tools import create_default_registry

    registry = create_default_registry(work_dir=Path("."))
    schemas = registry.get_tool_schemas()

    assert len(schemas) == 5
    names = {s["function"]["name"] for s in schemas}
    assert names == {"read_file", "write_file", "bash", "glob", "grep"}

    for schema in schemas:
        assert schema["type"] == "function"
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]
