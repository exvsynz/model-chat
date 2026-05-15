import pytest

from core.store import ConversationStore


@pytest.fixture
def store(tmp_path):
    return ConversationStore(tmp_path / "conversations")


def test_save_and_load(store):
    convo = {
        "id": "test-convo-1",
        "model": "openai/gpt-4o",
        "persona": "general",
        "created_at": "2026-05-03T14:00:00Z",
        "updated_at": "2026-05-03T14:05:00Z",
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ],
    }
    store.save(convo)
    loaded = store.load("test-convo-1")
    assert loaded["model"] == "openai/gpt-4o"
    assert len(loaded["messages"]) == 2


def test_load_not_found(store):
    assert store.load("nonexistent") is None


def test_list_all_empty(store):
    assert store.list_all() == []


def test_list_all(store):
    for i in range(3):
        store.save(
            {
                "id": f"convo-{i}",
                "model": "openai/gpt-4o",
                "persona": "general",
                "created_at": f"2026-05-03T14:0{i}:00Z",
                "updated_at": f"2026-05-03T14:0{i}:00Z",
                "messages": [],
            }
        )
    summaries = store.list_all()
    assert len(summaries) == 3
    assert all("id" in s for s in summaries)


def test_delete(store):
    store.save(
        {
            "id": "to-delete",
            "model": "x",
            "persona": "general",
            "created_at": "",
            "updated_at": "",
            "messages": [],
        }
    )
    assert store.load("to-delete") is not None
    store.delete("to-delete")
    assert store.load("to-delete") is None
