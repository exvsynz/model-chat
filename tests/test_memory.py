import pytest
from pathlib import Path
from core.memory import MemoryStore


@pytest.fixture
def memory(tmp_path):
    return MemoryStore(tmp_path / "memory")


def test_add_creates_file_and_index(memory):
    filename = memory.add("User is Josh from Taiwan", "user")
    assert filename == "user_josh_from_taiwan.md"
    assert (memory.memory_dir / filename).exists()
    assert (memory.memory_dir / "MEMORY.md").exists()


def test_list_all_returns_memories(memory):
    memory.add("User is Josh", "user")
    memory.add("Prefers dark mode", "preference")
    result = memory.list_all()
    assert len(result) == 2
    assert result[0]["file"] == "user_josh.md"


def test_remove_deletes_file_and_updates_index(memory):
    memory.add("User is Josh", "user")
    assert memory.remove("user_josh") is True
    assert not (memory.memory_dir / "user_josh.md").exists()
    assert memory.list_all() == []


def test_remove_nonexistent_returns_false(memory):
    assert memory.remove("nonexistent") is False


def test_format_for_prompt_returns_none_when_empty(memory):
    assert memory.format_for_prompt() is None


def test_format_for_prompt_returns_section(memory):
    memory.add("User is Josh from Taiwan", "user")
    memory.add("Prefers GUI tools", "preference")
    result = memory.format_for_prompt()
    assert "## Memories about the user" in result
    assert "Josh from Taiwan" in result
    assert "GUI tools" in result


def test_get_returns_memory_details(memory):
    memory.add("User is Josh from Taiwan", "user")
    result = memory.get("user_josh_from_taiwan")
    assert result is not None
    assert result["type"] == "user"
    assert "Josh from Taiwan" in result["content"]
    assert "created" in result


def test_get_nonexistent_returns_none(memory):
    assert memory.get("nonexistent") is None
