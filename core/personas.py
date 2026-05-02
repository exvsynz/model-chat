from pathlib import Path


class PersonaStore:
    def __init__(self, personas_dir: Path):
        self._dir = personas_dir

    @classmethod
    def from_bundled(cls) -> "PersonaStore":
        bundled = Path(__file__).parent.parent / "config" / "personas"
        return cls(bundled)

    def load(self, name: str) -> str | None:
        path = self._dir / f"{name}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        return None

    def list_names(self) -> list[str]:
        if not self._dir.exists():
            return []
        return sorted(p.stem for p in self._dir.glob("*.txt"))
