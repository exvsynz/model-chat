import re
from datetime import datetime, timezone
from pathlib import Path

STOPWORDS = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
             "have", "has", "had", "do", "does", "did", "will", "would", "could",
             "should", "may", "might", "shall", "can", "to", "of", "in", "for",
             "on", "with", "at", "by", "as", "into", "through", "during",
             "before", "after", "and", "but", "or", "not", "no", "so", "if", "then",
             "than", "that", "this", "it", "its", "i", "my", "me", "we", "our",
             "you", "your", "they", "their", "he", "she", "his", "her"}


class MemoryStore:
    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir

    def _ensure_dir(self):
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def add(self, content: str, memory_type: str = "fact") -> str:
        self._ensure_dir()
        slug = self._generate_slug(content, memory_type)
        filename = f"{slug}.md"
        now = datetime.now(timezone.utc).isoformat()
        file_content = f"---\ntype: {memory_type}\ncreated: {now}\n---\n\n{content}\n"
        (self.memory_dir / filename).write_text(file_content, encoding="utf-8")
        summary = content[:100]
        self._update_index(filename, summary)
        return filename

    def remove(self, slug: str) -> bool:
        filename = f"{slug}.md"
        path = self.memory_dir / filename
        if not path.exists():
            return False
        path.unlink()
        self._remove_from_index(filename)
        return True

    def list_all(self) -> list[dict]:
        index_path = self.memory_dir / "MEMORY.md"
        if not index_path.exists():
            return []
        entries = []
        for line in index_path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^- \[(.+?)\] (.+)$", line)
            if match:
                entries.append({"file": match.group(1), "summary": match.group(2)})
        return entries

    def get(self, slug: str) -> dict | None:
        filename = f"{slug}.md"
        path = self.memory_dir / filename
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        meta, body = self._parse_frontmatter(text)
        return {
            "type": meta.get("type", "fact"),
            "created": meta.get("created", ""),
            "content": body.strip(),
        }

    def format_for_prompt(self) -> str | None:
        entries = self.list_all()
        if not entries:
            return None
        lines = ["## Memories about the user\n"]
        for entry in entries:
            lines.append(f"- {entry['summary'][:200]}")
        return "\n".join(lines)

    def _is_duplicate(self, content: str) -> bool:
        words = self._significant_words(content)
        for entry in self.list_all():
            existing_words = self._significant_words(entry["summary"])
            overlap = words & existing_words
            if len(overlap) >= 3:
                return True
        return False

    def _generate_slug(self, content: str, memory_type: str) -> str:
        words = re.findall(r"[a-z0-9]+", content.lower())
        meaningful = [w for w in words if w not in STOPWORDS and len(w) > 1 and w != memory_type][:6]
        slug = f"{memory_type}_{'_'.join(meaningful)}"
        slug = slug[:50]
        if (self.memory_dir / f"{slug}.md").exists():
            i = 2
            while (self.memory_dir / f"{slug}_{i}.md").exists():
                i += 1
            slug = f"{slug}_{i}"
        return slug

    def _rebuild_index(self):
        self._ensure_dir()
        entries = []
        for path in sorted(self.memory_dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            text = path.read_text(encoding="utf-8")
            _, body = self._parse_frontmatter(text)
            summary = body.strip()[:100]
            entries.append(f"- [{path.name}] {summary}")
        index_path = self.memory_dir / "MEMORY.md"
        index_path.write_text("\n".join(entries) + "\n" if entries else "", encoding="utf-8")

    def _update_index(self, filename: str, summary: str):
        index_path = self.memory_dir / "MEMORY.md"
        line = f"- [{filename}] {summary}"
        if index_path.exists():
            content = index_path.read_text(encoding="utf-8")
            content = content.rstrip("\n") + "\n" + line + "\n"
        else:
            content = line + "\n"
        index_path.write_text(content, encoding="utf-8")

    def _remove_from_index(self, filename: str):
        index_path = self.memory_dir / "MEMORY.md"
        if not index_path.exists():
            return
        lines = index_path.read_text(encoding="utf-8").splitlines()
        lines = [l for l in lines if f"[{filename}]" not in l]
        index_path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

    def _significant_words(self, text: str) -> set[str]:
        words = set(re.findall(r"[a-z0-9]+", text.lower()))
        return words - STOPWORDS

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                meta = {}
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        key, val = line.split(":", 1)
                        meta[key.strip()] = val.strip()
                return meta, parts[2]
        return {}, text
