import pytest
from cli.commands import parse_command, CommandRegistry


@pytest.fixture
def registry():
    return CommandRegistry()


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
