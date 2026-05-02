import pytest
from core.models import ModelRegistry


@pytest.fixture
def registry(tmp_path):
    config = tmp_path / "models.yaml"
    config.write_text(
        "aliases:\n"
        "  gpt-4o: openai/gpt-4o\n"
        "  deepseek: deepseek/deepseek-v4-flash\n"
        "default: deepseek/deepseek-v4-flash\n"
    )
    return ModelRegistry(config)


def test_resolve_alias(registry):
    assert registry.resolve("gpt-4o") == "openai/gpt-4o"


def test_resolve_full_id_passthrough(registry):
    assert registry.resolve("anthropic/claude-sonnet-4-6") == "anthropic/claude-sonnet-4-6"


def test_resolve_unknown_alias_treated_as_full_id(registry):
    assert registry.resolve("meta-llama/llama-4-maverick") == "meta-llama/llama-4-maverick"


def test_default_model(registry):
    assert registry.default == "deepseek/deepseek-v4-flash"


def test_list_aliases(registry):
    aliases = registry.list_aliases()
    assert ("gpt-4o", "openai/gpt-4o") in aliases
    assert ("deepseek", "deepseek/deepseek-v4-flash") in aliases


def test_load_bundled_config():
    registry = ModelRegistry.from_bundled()
    assert registry.resolve("gpt-4o") == "openai/gpt-4o"
    assert registry.default is not None
