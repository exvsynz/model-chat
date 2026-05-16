from __future__ import annotations

import fnmatch
import logging
import shutil
from pathlib import Path

logger = logging.getLogger("model-chat.safety")

SENSITIVE_ENV_PATTERNS = [
    "*_KEY",
    "*_SECRET",
    "*_TOKEN",
    "*_PASSWORD",
    "OPENROUTER_*",
    "BRAVE_*",
    "AWS_*",
    "GITHUB_*",
    "AZURE_*",
    "GCP_*",
    "GOOGLE_*",
    "DATABASE_URL",
    "REDIS_URL",
    "MONGO_URI",
]

DEFAULT_TOOL_TIMEOUTS: dict[str, int] = {
    "shell": 120,
    "web_search": 15,
    "read_file": 10,
    "write_file": 10,
    "edit_file": 10,
    "glob": 10,
    "grep": 30,
}

MAX_OUTPUT_SIZE = 50_000
MAX_WRITE_SIZE = 1_048_576  # 1 MB
MAX_BACKUPS = 50
BACKUP_DIR_NAME = ".model-chat-backups"

_BINARY_EXTENSIONS = frozenset(
    {
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".dat",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".svg",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".mov",
        ".mkv",
        ".flac",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".pyc",
        ".pyo",
        ".class",
        ".o",
        ".obj",
    }
)


def sanitize_env(
    base_env: dict[str, str],
    allow_patterns: list[str] | None = None,
) -> dict[str, str]:
    """Strip env vars matching sensitive patterns. Keep everything else."""
    cleaned = {}
    for key, value in base_env.items():
        if _is_sensitive_var(key) and not _is_explicitly_allowed(key, allow_patterns):
            logger.debug("stripped env var: %s", key)
            continue
        cleaned[key] = value
    return cleaned


def _is_sensitive_var(key: str) -> bool:
    upper = key.upper()
    return any(fnmatch.fnmatch(upper, p) for p in SENSITIVE_ENV_PATTERNS)


def _is_explicitly_allowed(key: str, allow_patterns: list[str] | None) -> bool:
    if not allow_patterns:
        return False
    upper = key.upper()
    return any(fnmatch.fnmatch(upper, p.upper()) for p in allow_patterns)


def get_tool_timeout(tool_name: str) -> int:
    return DEFAULT_TOOL_TIMEOUTS.get(tool_name, 30)


def truncate_output(output: str, max_size: int = MAX_OUTPUT_SIZE) -> str:
    if len(output) <= max_size:
        return output
    return output[:max_size] + f"\n\n[truncated — output exceeded {max_size} characters]"


def check_write_safety(content: str, target: Path) -> str | None:
    """Returns error string if write should be blocked, None if OK."""
    size = len(content.encode("utf-8"))
    if size > MAX_WRITE_SIZE:
        return f"Error: write rejected — content is {size:,} bytes, max is {MAX_WRITE_SIZE:,}"
    if target.exists() and target.suffix.lower() in _BINARY_EXTENSIONS:
        return f"Error: write rejected — refusing to overwrite binary file {target.name}"
    return None


def backup_file(file_path: Path, work_dir: Path) -> Path | None:
    """Copy existing file to backup dir before overwrite. Returns backup path or None."""
    if not file_path.exists():
        return None
    backup_dir = work_dir / BACKUP_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        rel = file_path.resolve().relative_to(work_dir.resolve())
    except ValueError:
        rel = Path(file_path.name)

    safe_name = str(rel).replace("/", "__").replace("\\", "__")
    import time

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_name = f"{timestamp}__{safe_name}"
    backup_path = backup_dir / backup_name

    try:
        shutil.copy2(file_path, backup_path)
        logger.debug("backed up %s → %s", file_path, backup_path)
    except OSError as e:
        logger.warning("backup failed for %s: %s", file_path, e)
        return None

    _prune_backups(backup_dir)
    return backup_path


def _prune_backups(backup_dir: Path) -> None:
    backups = sorted(backup_dir.iterdir(), key=lambda p: p.stat().st_mtime)
    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        try:
            oldest.unlink()
            logger.debug("pruned old backup: %s", oldest.name)
        except OSError:
            pass
