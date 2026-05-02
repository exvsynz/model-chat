import pytest
from core.personas import PersonaStore


@pytest.fixture
def store(tmp_path):
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    (personas_dir / "general.txt").write_text("You are helpful.")
    (personas_dir / "coder.txt").write_text("You are a coder.")
    return PersonaStore(personas_dir)


def test_load_persona(store):
    assert store.load("general") == "You are helpful."


def test_load_persona_not_found(store):
    assert store.load("nonexistent") is None


def test_list_personas(store):
    names = store.list_names()
    assert "general" in names
    assert "coder" in names


def test_load_bundled():
    store = PersonaStore.from_bundled()
    assert store.load("general") is not None
    assert store.load("coder") is not None
