import os
import time
from pathlib import Path

import yaml
from openai import OpenAI


class ModelRegistry:
    def __init__(self, config_path: Path):
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self._aliases: dict[str, str] = data.get("aliases", {})
        self.default: str = data.get("default", "deepseek/deepseek-v4-flash")
        self._memory: dict = data.get("memory", {})

    @classmethod
    def from_bundled(cls) -> "ModelRegistry":
        config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        return cls(config_path)

    def resolve(self, name: str) -> str:
        return self._aliases.get(name, name)

    def list_aliases(self) -> list[tuple[str, str]]:
        return list(self._aliases.items())

    @property
    def memory_config(self) -> dict:
        return {
            "auto_memory": self._memory.get("auto_memory", True),
            "extraction_model": self._memory.get("extraction_model", None),
            "max_memories": self._memory.get("max_memories", 100),
        }


_all_models_cache: list[dict] | None = None
_all_models_cache_time: float = 0
_CACHE_TTL = 300


def fetch_all_models() -> list[dict]:
    global _all_models_cache, _all_models_cache_time
    if _all_models_cache and (time.time() - _all_models_cache_time) < _CACHE_TTL:
        return _all_models_cache

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    resp = client.models.list()
    models = [{"id": m.id, "name": getattr(m, "name", m.id)} for m in resp.data]
    models.sort(key=lambda m: m["id"])
    _all_models_cache = models
    _all_models_cache_time = time.time()
    return models
