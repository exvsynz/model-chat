import pytest
from cli.commands import parse_command, CommandRegistry, CommandHandler
from core.models import ModelRegistry
from core.personas import PersonaStore
from core.store import ConversationStore
from pathlib import Path


@pytest.fixture
def registry():
    return CommandRegistry()


@pytest.fixture
def handler(tmp_path):
    config_path = Path(__file__).parent.parent / "config" / "models.yaml"
    models = ModelRegistry(config_path)
    personas_dir = Path(__file__).parent.parent / "config" / "personas"
    personas = PersonaStore(personas_dir)
    store = ConversationStore(tmp_path / "convos")
    return CommandHandler(models=models, personas=personas, store=store)


def test_parse_slash_command():
    cmd, args = parse_command("/model gpt-4o")
    assert cmd == "model"
    assert args == "gpt-4o"


def test_parse_slash_command_no_args():
    cmd, args = parse_command("/help")
    assert cmd == "help"
    assert args == ""


def test_parse_not_a_command():
    cmd, args = parse_command("hello world")
    assert cmd is None
    assert args == "hello world"


def test_parse_slash_with_extra_spaces():
    cmd, args = parse_command("/model   gpt-4o  ")
    assert cmd == "model"
    assert args == "gpt-4o"


def test_registry_has_builtin_commands(registry):
    names = registry.list_commands()
    assert "model" in names
    assert "models" in names
    assert "effort" in names
    assert "file" in names
    assert "persona" in names
    assert "personas" in names
    assert "save" in names
    assert "load" in names
    assert "list" in names
    assert "clear" in names
    assert "multi" in names
    assert "help" in names
    assert "quit" in names


def test_registry_get_help(registry):
    help_text = registry.get_help()
    assert "/model" in help_text
    assert "/help" in help_text


# Task 7 test
def test_cmd_info_shows_current_state(handler, capsys):
    handler.current_model = "deepseek/deepseek-v4-flash"
    handler.persona_name = "coder"
    handler.effort = "high"
    handler.messages = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    handler.handle("info", "")
    output = capsys.readouterr().out
    assert "deepseek-v4-flash" in output
    assert "coder" in output
    assert "high" in output
    assert "2" in output


# Task 8 tests
def test_cmd_retry_returns_signal(handler):
    handler.messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    result = handler.handle("retry", "")
    assert result == "retry"
    assert len(handler.messages) == 1
    assert handler.messages[0]["role"] == "user"


def test_cmd_retry_empty_history(handler, capsys):
    handler.messages = []
    result = handler.handle("retry", "")
    assert result is None
    assert "No messages" in capsys.readouterr().out


# Task 9 tests
def test_cmd_edit_returns_signal(handler):
    handler.messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    result = handler.handle("edit", "")
    assert result == "edit"
    assert len(handler.messages) == 0
    assert handler.edit_text == "hello"


def test_cmd_edit_empty_history(handler, capsys):
    handler.messages = []
    result = handler.handle("edit", "")
    assert result is None
    assert "No messages" in capsys.readouterr().out


# Task 10 tests
def test_cmd_copy_copies_last_response(handler, capsys):
    handler.last_response = "hi there"
    from unittest.mock import patch, MagicMock
    with patch("cli.commands.subprocess") as mock_sp:
        mock_sp.run = MagicMock()
        handler.handle("copy", "")
    output = capsys.readouterr().out
    assert "Copied" in output


def test_cmd_copy_no_response(handler, capsys):
    handler.handle("copy", "")
    assert "No response" in capsys.readouterr().out


# Task 11 tests
def test_cmd_export_writes_markdown(handler, tmp_path, capsys):
    handler.messages = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language."},
    ]
    handler.current_model = "deepseek/deepseek-v4-flash"
    output_path = str(tmp_path / "export.md")
    handler.handle("export", output_path)
    output = capsys.readouterr().out
    assert "Exported" in output
    content = (tmp_path / "export.md").read_text(encoding="utf-8")
    assert "What is Python?" in content
    assert "Python is a programming language." in content


def test_cmd_export_no_messages(handler, capsys):
    handler.messages = []
    handler.handle("export", "test.md")
    assert "No messages" in capsys.readouterr().out
