import pytest
from unittest.mock import MagicMock
from prompt_toolkit.document import Document
from prompt_toolkit.completion import CompleteEvent
from cli.completers import ChatCompleter


@pytest.fixture
def completer():
    handler = MagicMock()
    handler.registry.list_commands.return_value = ["model", "persona", "help", "quit", "file", "load"]
    handler.models.list_aliases.return_value = [("deepseek-r1", "deepseek/deepseek-r1"), ("gpt-4o", "openai/gpt-4o")]
    handler.personas.list_names.return_value = ["coder", "tutor", "general"]
    handler.store.list_all.return_value = [{"id": "2026-05-01_chat1"}, {"id": "2026-05-02_chat2"}]
    return ChatCompleter(handler)


def test_completes_slash_commands(completer):
    doc = Document("/mo")
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    texts = [c.text for c in completions]
    assert "/model" in texts


def test_completes_model_names(completer):
    doc = Document("/model dee")
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    texts = [c.text for c in completions]
    assert "deepseek-r1" in texts


def test_completes_persona_names(completer):
    doc = Document("/persona co")
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    texts = [c.text for c in completions]
    assert "coder" in texts


def test_completes_load_ids(completer):
    doc = Document("/load 2026")
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    texts = [c.text for c in completions]
    assert "2026-05-01_chat1" in texts
    assert "2026-05-02_chat2" in texts


def test_no_completions_for_regular_text(completer):
    doc = Document("hello world")
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    assert len(completions) == 0
