import json
from pathlib import Path


class ConversationStore:
    def __init__(self, store_dir: Path):
        self._dir = store_dir

    def _ensure_dir(self):
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, conversation: dict) -> None:
        self._ensure_dir()
        path = self._dir / f"{conversation['id']}.json"
        path.write_text(json.dumps(conversation, indent=2, ensure_ascii=False), encoding="utf-8")

    def load(self, convo_id: str) -> dict | None:
        path = self._dir / f"{convo_id}.json"
        if not path.exists():
            return None
        result: dict = json.loads(path.read_text(encoding="utf-8"))
        return result

    def list_all(self) -> list[dict]:
        if not self._dir.exists():
            return []
        summaries = []
        for path in sorted(self._dir.glob("*.json"), reverse=True):
            data = json.loads(path.read_text(encoding="utf-8"))
            summaries.append(
                {
                    "id": data["id"],
                    "model": data.get("model", ""),
                    "persona": data.get("persona", ""),
                    "title": data.get("title", ""),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "message_count": len(data.get("messages", [])),
                }
            )
        return summaries

    def delete(self, convo_id: str) -> None:
        path = self._dir / f"{convo_id}.json"
        if path.exists():
            path.unlink()
