from pathlib import Path
import yaml


class ModelRegistry:
    def __init__(self, config_path: Path):
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self._aliases: dict[str, str] = data.get("aliases", {})
        self.default: str = data.get("default", "deepseek/deepseek-v4-flash")

    @classmethod
    def from_bundled(cls) -> "ModelRegistry":
        config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        return cls(config_path)

    def resolve(self, name: str) -> str:
        return self._aliases.get(name, name)

    def list_aliases(self) -> list[tuple[str, str]]:
        return list(self._aliases.items())
