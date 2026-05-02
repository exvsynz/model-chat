# Model Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal chat client powered by OpenRouter with a CLI REPL and a web UI for chatting with any LLM.

**Architecture:** Three packages in a monorepo — `core` (shared Python library for OpenRouter client, conversation storage, model registry, personas), `cli` (prompt_toolkit REPL), and `web` (FastAPI backend + SvelteKit frontend). The web frontend is pre-built to static files served by FastAPI so no Node is needed at runtime.

**Tech Stack:** Python 3.12, OpenAI SDK (for OpenRouter), prompt_toolkit, Rich, FastAPI, uvicorn, sse-starlette, PyYAML, SvelteKit, Tailwind CSS.

---

## File Map

### Core Library
| File | Responsibility |
|---|---|
| `core/__init__.py` | Package exports |
| `core/client.py` | Async streaming OpenRouter client via OpenAI SDK |
| `core/models.py` | Model alias registry, resolves aliases to full OpenRouter IDs |
| `core/store.py` | Conversation save/load/list/delete to JSON files |
| `core/personas.py` | Load/list persona system prompts from text files |

### CLI
| File | Responsibility |
|---|---|
| `cli/__init__.py` | Package exports |
| `cli/app.py` | REPL main loop, argument parsing, entry point |
| `cli/commands.py` | Slash command registry, individual command handlers |
| `cli/render.py` | Rich-based markdown and syntax rendering for terminal output |

### Web Backend
| File | Responsibility |
|---|---|
| `web/__init__.py` | Package exports |
| `web/backend/__init__.py` | Package exports |
| `web/backend/server.py` | FastAPI app, SSE chat endpoint, static file serving, entry point |

### Web Frontend
| File | Responsibility |
|---|---|
| `web/frontend/src/routes/+page.svelte` | Main chat page, composes all components |
| `web/frontend/src/routes/+layout.svelte` | Root layout, global styles |
| `web/frontend/src/lib/Chat.svelte` | Chat message panel with markdown rendering |
| `web/frontend/src/lib/Sidebar.svelte` | Conversation history sidebar |
| `web/frontend/src/lib/TopBar.svelte` | Model dropdown, effort toggle, persona selector |
| `web/frontend/src/lib/api.ts` | Fetch helpers for backend API + SSE streaming |
| `web/frontend/src/app.css` | Global Tailwind styles |
| `web/frontend/src/app.html` | HTML shell |

### Config & Packaging
| File | Responsibility |
|---|---|
| `config/models.yaml` | Default model alias registry |
| `config/personas/general.txt` | Default general persona |
| `config/personas/coder.txt` | Default coder persona |
| `pyproject.toml` | Python packaging, dependencies, CLI entry points |
| `.gitignore` | Python, Node, IDE ignores |
| `Dockerfile` | Optional container deploy |
| `README.md` | Install and usage instructions |

### Tests
| File | Responsibility |
|---|---|
| `tests/__init__.py` | Package |
| `tests/test_models.py` | Model registry resolution tests |
| `tests/test_store.py` | Conversation save/load/list/delete tests |
| `tests/test_personas.py` | Persona load/list tests |
| `tests/test_client.py` | OpenRouter client tests (mocked API) |
| `tests/test_commands.py` | CLI slash command parsing/dispatch tests |
| `tests/test_server.py` | FastAPI endpoint tests |

---

## Task 1: Project Scaffold & Packaging

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `config/models.yaml`
- Create: `config/personas/general.txt`
- Create: `config/personas/coder.txt`
- Create: `core/__init__.py`
- Create: `cli/__init__.py`
- Create: `web/__init__.py`
- Create: `web/backend/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd C:\Users\exvsy\model-chat
git init
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
.env
node_modules/
web/frontend/.svelte-kit/
web/frontend/build/
web/static/
.pytest_cache/
*.log
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "model-chat"
version = "1.0.0"
description = "Chat with any LLM via OpenRouter — CLI and web UI"
requires-python = ">=3.10"
dependencies = [
    "openai>=1.0",
    "prompt-toolkit>=3.0",
    "rich>=13.0",
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "sse-starlette>=1.6",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "httpx>=0.27"]

[project.scripts]
mchat = "cli.app:main"
mchat-web = "web.backend.server:main"

[tool.setuptools.packages.find]
include = ["core*", "cli*", "web*"]

[tool.setuptools.package-data]
"*" = ["*.yaml", "*.txt"]
```

- [ ] **Step 4: Create `config/models.yaml`**

```yaml
aliases:
  deepseek-v4-flash: deepseek/deepseek-v4-flash
  deepseek-r1: deepseek/deepseek-r1
  gpt-4o: openai/gpt-4o
  gpt-4o-mini: openai/gpt-4o-mini
  o3: openai/o3
  gemini-2.5-flash: google/gemini-2.5-flash
  gemini-2.5-pro: google/gemini-2.5-pro
  claude-sonnet: anthropic/claude-sonnet-4-6
  claude-haiku: anthropic/claude-haiku-4-5-20251001
  llama-4-maverick: meta-llama/llama-4-maverick
  qwen3-235b: qwen/qwen3-235b-a22b

default: deepseek/deepseek-v4-flash
```

- [ ] **Step 5: Create default persona files**

`config/personas/general.txt`:
```
You are a helpful assistant. Be concise and direct.
```

`config/personas/coder.txt`:
```
You are an expert programmer. Write clean, correct code. Explain concisely. Use markdown code blocks with language tags.
```

- [ ] **Step 6: Create package `__init__.py` files**

`core/__init__.py`:
```python
"""Core library — OpenRouter client, model registry, conversation store, personas."""
```

`cli/__init__.py`:
```python
"""CLI — interactive REPL for chatting with LLMs."""
```

`web/__init__.py`:
```python
"""Web — FastAPI backend and SvelteKit frontend."""
```

`web/backend/__init__.py`:
```python
"""Web backend — FastAPI server."""
```

`tests/__init__.py`:
```python
```

- [ ] **Step 7: Install in editable mode**

```bash
cd C:\Users\exvsy\model-chat
pip install -e ".[dev]"
```

- [ ] **Step 8: Verify install**

```bash
python -c "import core; import cli; import web; print('All packages import OK')"
```

- [ ] **Step 9: Commit**

```bash
git add .gitignore pyproject.toml config/ core/__init__.py cli/__init__.py web/__init__.py web/backend/__init__.py tests/__init__.py
git commit -m "feat: project scaffold with packaging, config, and default personas"
```

---

## Task 2: Model Registry (`core/models.py`)

**Files:**
- Create: `core/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_models.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:\Users\exvsy\model-chat
pytest tests/test_models.py -v
```

Expected: FAIL — `cannot import name 'ModelRegistry' from 'core.models'`

- [ ] **Step 3: Implement `core/models.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: model registry with alias resolution and bundled config"
```

---

## Task 3: Persona Store (`core/personas.py`)

**Files:**
- Create: `core/personas.py`
- Create: `tests/test_personas.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_personas.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_personas.py -v
```

Expected: FAIL — `cannot import name 'PersonaStore'`

- [ ] **Step 3: Implement `core/personas.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_personas.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/personas.py tests/test_personas.py
git commit -m "feat: persona store — load and list system prompt templates"
```

---

## Task 4: Conversation Store (`core/store.py`)

**Files:**
- Create: `core/store.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_store.py`:
```python
import json
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
        store.save({
            "id": f"convo-{i}",
            "model": "openai/gpt-4o",
            "persona": "general",
            "created_at": f"2026-05-03T14:0{i}:00Z",
            "updated_at": f"2026-05-03T14:0{i}:00Z",
            "messages": [],
        })
    summaries = store.list_all()
    assert len(summaries) == 3
    assert all("id" in s for s in summaries)


def test_delete(store):
    store.save({"id": "to-delete", "model": "x", "persona": "general",
                "created_at": "", "updated_at": "", "messages": []})
    assert store.load("to-delete") is not None
    store.delete("to-delete")
    assert store.load("to-delete") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_store.py -v
```

Expected: FAIL — `cannot import name 'ConversationStore'`

- [ ] **Step 3: Implement `core/store.py`**

```python
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
        return json.loads(path.read_text(encoding="utf-8"))

    def list_all(self) -> list[dict]:
        if not self._dir.exists():
            return []
        summaries = []
        for path in sorted(self._dir.glob("*.json"), reverse=True):
            data = json.loads(path.read_text(encoding="utf-8"))
            summaries.append({
                "id": data["id"],
                "model": data.get("model", ""),
                "persona": data.get("persona", ""),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": len(data.get("messages", [])),
            })
        return summaries

    def delete(self, convo_id: str) -> None:
        path = self._dir / f"{convo_id}.json"
        if path.exists():
            path.unlink()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_store.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/store.py tests/test_store.py
git commit -m "feat: conversation store — save, load, list, delete JSON conversations"
```

---

## Task 5: OpenRouter Streaming Client (`core/client.py`)

**Files:**
- Create: `core/client.py`
- Create: `tests/test_client.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_client.py`:
```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from core.client import chat_stream, ChatError


@pytest.mark.asyncio
async def test_chat_stream_yields_tokens():
    mock_chunk_1 = MagicMock()
    mock_chunk_1.choices = [MagicMock()]
    mock_chunk_1.choices[0].delta.content = "Hello"

    mock_chunk_2 = MagicMock()
    mock_chunk_2.choices = [MagicMock()]
    mock_chunk_2.choices[0].delta.content = " world"

    mock_chunk_3 = MagicMock()
    mock_chunk_3.choices = [MagicMock()]
    mock_chunk_3.choices[0].delta.content = None

    async def mock_stream():
        for chunk in [mock_chunk_1, mock_chunk_2, mock_chunk_3]:
            yield chunk

    with patch("core.client.get_openai_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(return_value=mock_stream())
        mock_get_client.return_value = mock_client

        tokens = []
        async for token in chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/gpt-4o",
        ):
            tokens.append(token)

    assert tokens == ["Hello", " world"]


@pytest.mark.asyncio
async def test_chat_stream_with_system_prompt():
    async def mock_stream():
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "ok"
        yield chunk

    with patch("core.client.get_openai_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(return_value=mock_stream())
        mock_get_client.return_value = mock_client

        tokens = []
        async for token in chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/gpt-4o",
            system_prompt="You are helpful.",
        ):
            tokens.append(token)

        call_args = mock_client.chat.completions.create.call_args
        sent_messages = call_args.kwargs["messages"]
        assert sent_messages[0]["role"] == "system"
        assert sent_messages[0]["content"] == "You are helpful."


@pytest.mark.asyncio
async def test_chat_stream_with_effort():
    async def mock_stream():
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "ok"
        yield chunk

    with patch("core.client.get_openai_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(return_value=mock_stream())
        mock_get_client.return_value = mock_client

        async for _ in chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            model="deepseek/deepseek-r1",
            effort="high",
        ):
            pass

        call_args = mock_client.chat.completions.create.call_args
        extra_body = call_args.kwargs.get("extra_body", {})
        assert extra_body.get("reasoning_effort") == "high"


def test_missing_api_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ChatError, match="OPENROUTER_API_KEY"):
            from core.client import get_openai_client
            get_openai_client()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_client.py -v
```

Expected: FAIL — `cannot import name 'chat_stream'`

- [ ] **Step 3: Implement `core/client.py`**

```python
import os
from collections.abc import AsyncGenerator
from openai import OpenAI


class ChatError(Exception):
    pass


def get_openai_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ChatError("OPENROUTER_API_KEY environment variable not set")
    return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")


async def chat_stream(
    messages: list[dict],
    model: str,
    system_prompt: str | None = None,
    effort: str | None = None,
) -> AsyncGenerator[str, None]:
    client = get_openai_client()

    final_messages = []
    if system_prompt:
        final_messages.append({"role": "system", "content": system_prompt})
    final_messages.extend(messages)

    kwargs: dict = {
        "model": model,
        "messages": final_messages,
        "stream": True,
    }
    if effort:
        kwargs["extra_body"] = {"reasoning_effort": effort}

    stream = client.chat.completions.create(**kwargs)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_client.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/client.py tests/test_client.py
git commit -m "feat: OpenRouter streaming client with effort support"
```

---

## Task 6: CLI Markdown Renderer (`cli/render.py`)

**Files:**
- Create: `cli/render.py`

- [ ] **Step 1: Implement `cli/render.py`**

```python
from rich.console import Console
from rich.markdown import Markdown

_console = Console()


def print_markdown(text: str) -> None:
    _console.print(Markdown(text))


def print_streaming_token(token: str) -> None:
    _console.print(token, end="", highlight=False)


def print_streaming_end() -> None:
    _console.print()


def print_info(text: str) -> None:
    _console.print(f"[dim]{text}[/dim]")


def print_error(text: str) -> None:
    _console.print(f"[bold red]Error:[/bold red] {text}")


def print_success(text: str) -> None:
    _console.print(f"[green]{text}[/green]")
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from cli.render import print_markdown, print_info; print('render OK')"
```

- [ ] **Step 3: Commit**

```bash
git add cli/render.py
git commit -m "feat: CLI rich markdown renderer"
```

---

## Task 7: CLI Slash Commands (`cli/commands.py`)

**Files:**
- Create: `cli/commands.py`
- Create: `tests/test_commands.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_commands.py`:
```python
import pytest
from cli.commands import parse_command, CommandRegistry


@pytest.fixture
def registry():
    return CommandRegistry()


def test_parse_slash_command():
    cmd, args = parse_command("/model gpt-4o")
    assert cmd == "model"
    assert args == "gpt-4o"


def test_parse_slash_command_no_args():
    cmd, args = parse_command("/help")
    assert cmd == "help"
    assert args == ""


def test_parse_not_a_command():
    cmd, args = parse_command("hello world")
    assert cmd is None
    assert args == "hello world"


def test_parse_slash_with_extra_spaces():
    cmd, args = parse_command("/model   gpt-4o  ")
    assert cmd == "model"
    assert args == "gpt-4o"


def test_registry_has_builtin_commands(registry):
    names = registry.list_commands()
    assert "model" in names
    assert "models" in names
    assert "effort" in names
    assert "file" in names
    assert "persona" in names
    assert "personas" in names
    assert "save" in names
    assert "load" in names
    assert "list" in names
    assert "clear" in names
    assert "multi" in names
    assert "help" in names
    assert "quit" in names


def test_registry_get_help(registry):
    help_text = registry.get_help()
    assert "/model" in help_text
    assert "/help" in help_text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_commands.py -v
```

Expected: FAIL — `cannot import name 'parse_command'`

- [ ] **Step 3: Implement `cli/commands.py`**

```python
from pathlib import Path
from core.models import ModelRegistry
from core.personas import PersonaStore
from core.store import ConversationStore
from cli.render import print_info, print_error, print_success


def parse_command(text: str) -> tuple[str | None, str]:
    text = text.strip()
    if not text.startswith("/"):
        return None, text
    parts = text[1:].split(None, 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""
    return cmd, args


COMMAND_HELP = {
    "model": ("/model <name|id>", "Switch model"),
    "models": ("/models", "List available model aliases"),
    "effort": ("/effort low|medium|high", "Set reasoning effort"),
    "file": ("/file <path>", "Add file contents to context"),
    "persona": ("/persona <name>", "Load a system prompt"),
    "personas": ("/personas", "List available personas"),
    "save": ("/save", "Save current conversation"),
    "load": ("/load <id>", "Resume a saved conversation"),
    "list": ("/list", "List saved conversations"),
    "clear": ("/clear", "Reset conversation"),
    "multi": ("/multi", "Toggle multi-line input"),
    "help": ("/help", "Show this help"),
    "quit": ("/quit", "Exit"),
}


class CommandRegistry:
    def __init__(self):
        self._commands = COMMAND_HELP

    def list_commands(self) -> list[str]:
        return list(self._commands.keys())

    def get_help(self) -> str:
        lines = []
        for cmd, (usage, desc) in self._commands.items():
            lines.append(f"  {usage:<30} {desc}")
        return "\n".join(lines)


class CommandHandler:
    def __init__(
        self,
        models: ModelRegistry,
        personas: PersonaStore,
        store: ConversationStore,
    ):
        self.models = models
        self.personas = personas
        self.store = store
        self.current_model: str = models.default
        self.effort: str | None = None
        self.system_prompt: str | None = None
        self.persona_name: str | None = None
        self.messages: list[dict] = []
        self.multi_line: bool = False
        self.registry = CommandRegistry()

    def handle(self, cmd: str, args: str) -> str | None:
        handler = getattr(self, f"_cmd_{cmd}", None)
        if handler is None:
            print_error(f"Unknown command: /{cmd}")
            return None
        return handler(args)

    def _cmd_model(self, args: str) -> str | None:
        if not args:
            print_info(f"Current model: {self.current_model}")
            return None
        self.current_model = self.models.resolve(args)
        print_success(f"Switched to {self.current_model}")
        return None

    def _cmd_models(self, args: str) -> str | None:
        aliases = self.models.list_aliases()
        lines = [f"  {alias:<25} {full_id}" for alias, full_id in aliases]
        print_info("Available models:\n" + "\n".join(lines))
        return None

    def _cmd_effort(self, args: str) -> str | None:
        if args not in ("low", "medium", "high"):
            print_error("Usage: /effort low|medium|high")
            return None
        self.effort = args
        print_success(f"Effort set to {args}")
        return None

    def _cmd_file(self, args: str) -> str | None:
        if not args:
            print_error("Usage: /file <path>")
            return None
        path = Path(args).expanduser()
        if not path.exists():
            print_error(f"File not found: {path}")
            return None
        content = path.read_text(encoding="utf-8", errors="replace")
        line_count = len(content.splitlines())
        self.messages.append({
            "role": "user",
            "content": f"<file path=\"{path}\">\n{content}\n</file>",
        })
        print_success(f"Added {path.name} to context ({line_count} lines)")
        return None

    def _cmd_persona(self, args: str) -> str | None:
        if not args:
            if self.persona_name:
                print_info(f"Current persona: {self.persona_name}")
            else:
                print_info("No persona set")
            return None
        prompt = self.personas.load(args)
        if prompt is None:
            print_error(f"Persona not found: {args}")
            return None
        self.system_prompt = prompt
        self.persona_name = args
        print_success(f"Persona set to {args}")
        return None

    def _cmd_personas(self, args: str) -> str | None:
        names = self.personas.list_names()
        if not names:
            print_info("No personas found")
            return None
        print_info("Available personas: " + ", ".join(names))
        return None

    def _cmd_save(self, args: str) -> str | None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        model_short = self.current_model.split("/")[-1] if "/" in self.current_model else self.current_model
        convo_id = now.strftime(f"%Y-%m-%d_%H-%M-%S_{model_short}")
        convo = {
            "id": convo_id,
            "model": self.current_model,
            "persona": self.persona_name or "",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "messages": self.messages,
        }
        self.store.save(convo)
        print_success(f"Saved as {convo_id}")
        return None

    def _cmd_load(self, args: str) -> str | None:
        if not args:
            print_error("Usage: /load <id>")
            return None
        convo = self.store.load(args)
        if convo is None:
            print_error(f"Conversation not found: {args}")
            return None
        self.messages = convo.get("messages", [])
        self.current_model = convo.get("model", self.current_model)
        self.persona_name = convo.get("persona") or None
        if self.persona_name:
            self.system_prompt = self.personas.load(self.persona_name)
        print_success(f"Loaded {args} ({len(self.messages)} messages, model: {self.current_model})")
        return None

    def _cmd_list(self, args: str) -> str | None:
        summaries = self.store.list_all()
        if not summaries:
            print_info("No saved conversations")
            return None
        lines = []
        for s in summaries:
            lines.append(f"  {s['id']:<45} {s['model']:<30} {s['message_count']} msgs")
        print_info("Saved conversations:\n" + "\n".join(lines))
        return None

    def _cmd_clear(self, args: str) -> str | None:
        self.messages = []
        print_success("Conversation cleared")
        return None

    def _cmd_multi(self, args: str) -> str | None:
        self.multi_line = not self.multi_line
        state = "on" if self.multi_line else "off"
        print_success(f"Multi-line input {state} (Alt+Enter to submit)")
        return None

    def _cmd_help(self, args: str) -> str | None:
        print_info(self.registry.get_help())
        return None

    def _cmd_quit(self, args: str) -> str | None:
        return "quit"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_commands.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add cli/commands.py tests/test_commands.py
git commit -m "feat: CLI slash command registry and handlers"
```

---

## Task 8: CLI REPL App (`cli/app.py`)

**Files:**
- Create: `cli/app.py`

- [ ] **Step 1: Implement `cli/app.py`**

```python
import argparse
import asyncio
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory

from core.client import chat_stream, ChatError
from core.models import ModelRegistry
from core.personas import PersonaStore
from core.store import ConversationStore
from cli.commands import parse_command, CommandHandler
from cli.render import (
    print_markdown,
    print_streaming_token,
    print_streaming_end,
    print_info,
    print_error,
)


DATA_DIR = Path.home() / ".model-chat"


def get_prompt_session(handler: CommandHandler) -> PromptSession:
    commands = ["/" + c for c in handler.registry.list_commands()]
    completer = WordCompleter(commands, sentence=True)
    history_path = DATA_DIR / "history"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    return PromptSession(
        completer=completer,
        history=FileHistory(str(history_path)),
    )


async def run_chat(handler: CommandHandler, user_input: str) -> None:
    handler.messages.append({"role": "user", "content": user_input})

    full_response = ""
    try:
        async for token in chat_stream(
            messages=handler.messages,
            model=handler.current_model,
            system_prompt=handler.system_prompt,
            effort=handler.effort,
        ):
            print_streaming_token(token)
            full_response += token
        print_streaming_end()
        print()
    except ChatError as e:
        print_error(str(e))
        handler.messages.pop()
        return
    except Exception as e:
        print_error(f"API error: {e}")
        handler.messages.pop()
        return

    handler.messages.append({"role": "assistant", "content": full_response})


async def repl(handler: CommandHandler) -> None:
    session = get_prompt_session(handler)

    model_short = handler.current_model.split("/")[-1] if "/" in handler.current_model else handler.current_model
    print_info(f"model-chat v1.0 — type /help for commands\n")

    while True:
        model_short = handler.current_model.split("/")[-1] if "/" in handler.current_model else handler.current_model
        try:
            if handler.multi_line:
                user_input = session.prompt(
                    f"[{model_short}] > ",
                    multiline=True,
                )
            else:
                user_input = session.prompt(f"[{model_short}] > ")
        except (EOFError, KeyboardInterrupt):
            print_info("\nGoodbye!")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        cmd, args = parse_command(user_input)
        if cmd is not None:
            result = handler.handle(cmd, args)
            if result == "quit":
                print_info("Goodbye!")
                break
            continue

        await run_chat(handler, user_input)


def main():
    parser = argparse.ArgumentParser(description="Chat with any LLM via OpenRouter")
    parser.add_argument("--model", default=None, help="Starting model (alias or full ID)")
    parser.add_argument("--persona", default=None, help="Starting persona")
    parser.add_argument("--effort", choices=["low", "medium", "high"], default=None, help="Reasoning effort")
    parser.add_argument("--web", action="store_true", help="Launch web UI instead of CLI")
    args = parser.parse_args()

    if args.web:
        from web.backend.server import main as web_main
        web_main()
        return

    models = ModelRegistry.from_bundled()
    personas = PersonaStore.from_bundled()
    store = ConversationStore(DATA_DIR / "conversations")

    handler = CommandHandler(models=models, personas=personas, store=store)

    if args.model:
        handler.current_model = models.resolve(args.model)
    if args.persona:
        prompt = personas.load(args.persona)
        if prompt:
            handler.system_prompt = prompt
            handler.persona_name = args.persona
        else:
            print_error(f"Persona not found: {args.persona}")
    if args.effort:
        handler.effort = args.effort

    asyncio.run(repl(handler))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the CLI launches**

```bash
cd C:\Users\exvsy\model-chat
python -m cli.app --help
```

Expected: Shows argparse help text with `--model`, `--persona`, `--effort`, `--web` flags.

- [ ] **Step 3: Verify `mchat` entry point works**

```bash
mchat --help
```

Expected: Same help text. If not installed yet, re-run `pip install -e ".[dev]"`.

- [ ] **Step 4: Manual smoke test — launch and send one message**

```bash
mchat
```

Type `hello` and verify a streaming response comes back from the default model. Type `/quit` to exit.

- [ ] **Step 5: Commit**

```bash
git add cli/app.py
git commit -m "feat: CLI REPL with streaming chat, slash commands, and startup flags"
```

---

## Task 9: FastAPI Backend (`web/backend/server.py`)

**Files:**
- Create: `web/backend/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_server.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from web.backend.server import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_get_models(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "aliases" in data
    assert "default" in data


@pytest.mark.asyncio
async def test_get_personas(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/personas")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "general" in data


@pytest.mark.asyncio
async def test_get_conversations_empty(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/conversations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_chat_requires_messages(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/chat", json={"model": "openai/gpt-4o"})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_server.py -v
```

Expected: FAIL — `cannot import name 'create_app'`

- [ ] **Step 3: Implement `web/backend/server.py`**

```python
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from core.client import chat_stream
from core.models import ModelRegistry
from core.personas import PersonaStore
from core.store import ConversationStore


DATA_DIR = Path.home() / ".model-chat"


class ChatRequest(BaseModel):
    messages: list[dict]
    model: str
    persona: str | None = None
    effort: str | None = None


class SaveRequest(BaseModel):
    id: str
    model: str
    persona: str | None = None
    created_at: str
    updated_at: str
    messages: list[dict]


def create_app() -> FastAPI:
    app = FastAPI(title="model-chat")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    models = ModelRegistry.from_bundled()
    personas = PersonaStore.from_bundled()
    store = ConversationStore(DATA_DIR / "conversations")

    @app.get("/api/models")
    def get_models():
        return {
            "aliases": dict(models.list_aliases()),
            "default": models.default,
        }

    @app.get("/api/personas")
    def get_personas():
        return personas.list_names()

    @app.get("/api/conversations")
    def get_conversations():
        return store.list_all()

    @app.get("/api/conversations/{convo_id}")
    def get_conversation(convo_id: str):
        convo = store.load(convo_id)
        if convo is None:
            return {"error": "not found"}, 404
        return convo

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        system_prompt = None
        if req.persona:
            system_prompt = personas.load(req.persona)

        async def event_generator():
            async for token in chat_stream(
                messages=req.messages,
                model=req.model,
                system_prompt=system_prompt,
                effort=req.effort,
            ):
                yield {"data": json.dumps({"token": token})}
            yield {"data": json.dumps({"done": True})}

        return EventSourceResponse(event_generator())

    @app.post("/api/conversations/save")
    def save_conversation(req: SaveRequest):
        store.save(req.model_dump())
        return {"status": "saved", "id": req.id}

    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


def main():
    import argparse
    import webbrowser

    parser = argparse.ArgumentParser(description="model-chat web server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    webbrowser.open(f"http://{args.host}:{args.port}")
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_server.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add web/backend/server.py tests/test_server.py
git commit -m "feat: FastAPI backend with models, personas, conversations, and SSE chat"
```

---

## Task 10: SvelteKit Frontend — Project Setup

**Files:**
- Create: `web/frontend/` (SvelteKit project)

- [ ] **Step 1: Scaffold SvelteKit project**

```bash
cd C:\Users\exvsy\model-chat\web
npm create svelte@latest frontend -- --template skeleton --types typescript
```

Select: Skeleton project, TypeScript, no additional options.

- [ ] **Step 2: Install dependencies**

```bash
cd C:\Users\exvsy\model-chat\web\frontend
npm install
npm install -D tailwindcss @tailwindcss/typography @sveltejs/adapter-static
npm install marked highlight.js
```

- [ ] **Step 3: Configure `svelte.config.js` for static adapter**

Replace `web/frontend/svelte.config.js`:
```javascript
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/kit/vite';

export default {
	kit: {
		adapter: adapter({
			pages: '../static',
			assets: '../static',
			fallback: 'index.html'
		})
	},
	preprocess: vitePreprocess()
};
```

- [ ] **Step 4: Configure Tailwind in `web/frontend/src/app.css`**

```css
@import 'tailwindcss';

:root {
    color-scheme: dark;
}

body {
    @apply bg-zinc-900 text-zinc-100;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

pre code {
    @apply text-sm;
}
```

- [ ] **Step 5: Create `web/frontend/src/app.html`**

```html
<!doctype html>
<html lang="en" class="dark">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>model-chat</title>
    %sveltekit.head%
</head>
<body data-sveltekit-prerender="true">
    <div style="display: contents">%sveltekit.body%</div>
</body>
</html>
```

- [ ] **Step 6: Verify dev server starts**

```bash
cd C:\Users\exvsy\model-chat\web\frontend
npm run dev
```

Expected: SvelteKit dev server running on localhost.

- [ ] **Step 7: Commit**

```bash
cd C:\Users\exvsy\model-chat
git add web/frontend/package.json web/frontend/package-lock.json web/frontend/svelte.config.js web/frontend/src/app.css web/frontend/src/app.html web/frontend/tsconfig.json web/frontend/vite.config.ts
git commit -m "feat: SvelteKit frontend scaffold with Tailwind and static adapter"
```

---

## Task 11: Frontend API Client (`web/frontend/src/lib/api.ts`)

**Files:**
- Create: `web/frontend/src/lib/api.ts`

- [ ] **Step 1: Implement `api.ts`**

```typescript
const BASE = 'http://127.0.0.1:8000';

export interface ModelsResponse {
    aliases: Record<string, string>;
    default: string;
}

export interface ConversationSummary {
    id: string;
    model: string;
    persona: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}

export interface Message {
    role: 'user' | 'assistant' | 'system';
    content: string;
}

export async function fetchModels(): Promise<ModelsResponse> {
    const res = await fetch(`${BASE}/api/models`);
    return res.json();
}

export async function fetchPersonas(): Promise<string[]> {
    const res = await fetch(`${BASE}/api/personas`);
    return res.json();
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
    const res = await fetch(`${BASE}/api/conversations`);
    return res.json();
}

export async function loadConversation(id: string): Promise<{ messages: Message[]; model: string; persona: string }> {
    const res = await fetch(`${BASE}/api/conversations/${id}`);
    return res.json();
}

export async function saveConversation(convo: {
    id: string;
    model: string;
    persona: string | null;
    created_at: string;
    updated_at: string;
    messages: Message[];
}): Promise<void> {
    await fetch(`${BASE}/api/conversations/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(convo),
    });
}

export async function* streamChat(
    messages: Message[],
    model: string,
    persona: string | null,
    effort: string | null,
): AsyncGenerator<string, void> {
    const res = await fetch(`${BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages, model, persona, effort }),
    });

    if (!res.ok || !res.body) {
        throw new Error(`Chat request failed: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const payload = JSON.parse(line.slice(6));
                if (payload.done) return;
                if (payload.token) yield payload.token;
            }
        }
    }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd C:\Users\exvsy\model-chat\web\frontend
npx svelte-check
```

Expected: No errors in `api.ts`.

- [ ] **Step 3: Commit**

```bash
cd C:\Users\exvsy\model-chat
git add web/frontend/src/lib/api.ts
git commit -m "feat: frontend API client with SSE streaming"
```

---

## Task 12: TopBar Component (`web/frontend/src/lib/TopBar.svelte`)

**Files:**
- Create: `web/frontend/src/lib/TopBar.svelte`

- [ ] **Step 1: Implement `TopBar.svelte`**

```svelte
<script lang="ts">
    import type { ModelsResponse } from './api';

    export let models: ModelsResponse;
    export let personas: string[];
    export let currentModel: string;
    export let currentPersona: string | null;
    export let currentEffort: string | null;

    let aliasEntries: [string, string][] = [];
    $: aliasEntries = Object.entries(models.aliases);

    function onModelChange(e: Event) {
        const select = e.target as HTMLSelectElement;
        currentModel = select.value;
    }

    function onPersonaChange(e: Event) {
        const select = e.target as HTMLSelectElement;
        currentPersona = select.value || null;
    }

    function setEffort(level: string | null) {
        currentEffort = currentEffort === level ? null : level;
    }
</script>

<div class="flex items-center gap-4 px-4 py-2 bg-zinc-800 border-b border-zinc-700">
    <span class="text-sm font-semibold text-zinc-400">model-chat</span>

    <select
        value={currentModel}
        on:change={onModelChange}
        class="bg-zinc-700 text-zinc-100 text-sm rounded px-2 py-1 border border-zinc-600 focus:outline-none focus:border-zinc-400"
    >
        {#each aliasEntries as [alias, fullId]}
            <option value={fullId}>{alias}</option>
        {/each}
    </select>

    <div class="flex gap-1">
        {#each ['low', 'medium', 'high'] as level}
            <button
                class="px-2 py-1 text-xs rounded {currentEffort === level ? 'bg-blue-600 text-white' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'}"
                on:click={() => setEffort(level)}
            >
                {level}
            </button>
        {/each}
    </div>

    <select
        value={currentPersona || ''}
        on:change={onPersonaChange}
        class="bg-zinc-700 text-zinc-100 text-sm rounded px-2 py-1 border border-zinc-600 focus:outline-none focus:border-zinc-400"
    >
        <option value="">No persona</option>
        {#each personas as name}
            <option value={name}>{name}</option>
        {/each}
    </select>
</div>
```

- [ ] **Step 2: Commit**

```bash
cd C:\Users\exvsy\model-chat
git add web/frontend/src/lib/TopBar.svelte
git commit -m "feat: TopBar component — model dropdown, effort toggle, persona selector"
```

---

## Task 13: Chat Component (`web/frontend/src/lib/Chat.svelte`)

**Files:**
- Create: `web/frontend/src/lib/Chat.svelte`

- [ ] **Step 1: Implement `Chat.svelte`**

```svelte
<script lang="ts">
    import { onMount, afterUpdate } from 'svelte';
    import { marked } from 'marked';
    import hljs from 'highlight.js';
    import 'highlight.js/styles/github-dark.css';
    import type { Message } from './api';

    export let messages: Message[] = [];
    export let streamingContent: string = '';

    let chatContainer: HTMLDivElement;

    marked.setOptions({
        highlight(code: string, lang: string) {
            if (lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return hljs.highlightAuto(code).value;
        },
    });

    function renderMarkdown(text: string): string {
        return marked.parse(text) as string;
    }

    afterUpdate(() => {
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    });
</script>

<div bind:this={chatContainer} class="flex-1 overflow-y-auto px-4 py-6 space-y-6">
    {#each messages as msg}
        <div class="max-w-3xl mx-auto">
            {#if msg.role === 'user'}
                <div class="flex justify-end">
                    <div class="bg-zinc-700 rounded-2xl px-4 py-2 max-w-[80%]">
                        <p class="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                </div>
            {:else if msg.role === 'assistant'}
                <div class="prose prose-invert prose-sm max-w-none">
                    {@html renderMarkdown(msg.content)}
                </div>
            {/if}
        </div>
    {/each}

    {#if streamingContent}
        <div class="max-w-3xl mx-auto">
            <div class="prose prose-invert prose-sm max-w-none">
                {@html renderMarkdown(streamingContent)}
            </div>
        </div>
    {/if}

    {#if messages.length === 0 && !streamingContent}
        <div class="flex items-center justify-center h-full text-zinc-500">
            <p>Start a conversation</p>
        </div>
    {/if}
</div>
```

- [ ] **Step 2: Commit**

```bash
cd C:\Users\exvsy\model-chat
git add web/frontend/src/lib/Chat.svelte
git commit -m "feat: Chat component — message rendering with markdown and syntax highlighting"
```

---

## Task 14: Sidebar Component (`web/frontend/src/lib/Sidebar.svelte`)

**Files:**
- Create: `web/frontend/src/lib/Sidebar.svelte`

- [ ] **Step 1: Implement `Sidebar.svelte`**

```svelte
<script lang="ts">
    import type { ConversationSummary } from './api';

    export let conversations: ConversationSummary[] = [];
    export let onLoad: (id: string) => void;
    export let onNew: () => void;
</script>

<div class="w-64 bg-zinc-850 border-r border-zinc-700 flex flex-col h-full" style="background-color: rgb(20 20 20);">
    <div class="p-3">
        <button
            on:click={onNew}
            class="w-full bg-zinc-700 hover:bg-zinc-600 text-zinc-100 text-sm rounded-lg px-3 py-2 transition-colors"
        >
            + New Chat
        </button>
    </div>

    <div class="flex-1 overflow-y-auto px-2 space-y-1">
        {#each conversations as convo}
            <button
                on:click={() => onLoad(convo.id)}
                class="w-full text-left px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-700 transition-colors truncate"
                title={convo.id}
            >
                <div class="truncate">{convo.id}</div>
                <div class="text-xs text-zinc-500">{convo.model.split('/').pop()} · {convo.message_count} msgs</div>
            </button>
        {/each}

        {#if conversations.length === 0}
            <p class="text-xs text-zinc-500 px-3 py-2">No saved conversations</p>
        {/if}
    </div>
</div>
```

- [ ] **Step 2: Commit**

```bash
cd C:\Users\exvsy\model-chat
git add web/frontend/src/lib/Sidebar.svelte
git commit -m "feat: Sidebar component — conversation history list"
```

---

## Task 15: Main Page — Compose All Components (`web/frontend/src/routes/+page.svelte`)

**Files:**
- Create: `web/frontend/src/routes/+layout.svelte`
- Create: `web/frontend/src/routes/+page.svelte`

- [ ] **Step 1: Create root layout**

`web/frontend/src/routes/+layout.svelte`:
```svelte
<script>
    import '../app.css';
</script>

<slot />
```

- [ ] **Step 2: Implement the main page**

`web/frontend/src/routes/+page.svelte`:
```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    import TopBar from '$lib/TopBar.svelte';
    import Chat from '$lib/Chat.svelte';
    import Sidebar from '$lib/Sidebar.svelte';
    import {
        fetchModels,
        fetchPersonas,
        fetchConversations,
        loadConversation,
        saveConversation,
        streamChat,
        type ModelsResponse,
        type Message,
        type ConversationSummary,
    } from '$lib/api';

    let models: ModelsResponse = { aliases: {}, default: '' };
    let personas: string[] = [];
    let conversations: ConversationSummary[] = [];
    let messages: Message[] = [];
    let currentModel = '';
    let currentPersona: string | null = null;
    let currentEffort: string | null = null;
    let streamingContent = '';
    let inputText = '';
    let isStreaming = false;
    let inputEl: HTMLTextAreaElement;

    onMount(async () => {
        const [m, p, c] = await Promise.all([
            fetchModels(),
            fetchPersonas(),
            fetchConversations(),
        ]);
        models = m;
        personas = p;
        conversations = c;
        currentModel = m.default;
    });

    async function sendMessage() {
        const text = inputText.trim();
        if (!text || isStreaming) return;

        inputText = '';
        messages = [...messages, { role: 'user', content: text }];
        isStreaming = true;
        streamingContent = '';

        try {
            for await (const token of streamChat(messages, currentModel, currentPersona, currentEffort)) {
                streamingContent += token;
            }
            messages = [...messages, { role: 'assistant', content: streamingContent }];
            streamingContent = '';

            const now = new Date().toISOString();
            const modelShort = currentModel.includes('/') ? currentModel.split('/').pop() : currentModel;
            const id = `${now.slice(0, 19).replace(/[T:]/g, '-')}_${modelShort}`;
            await saveConversation({
                id,
                model: currentModel,
                persona: currentPersona,
                created_at: now,
                updated_at: now,
                messages,
            });
            conversations = await fetchConversations();
        } catch (e: any) {
            streamingContent = '';
            messages = [...messages, { role: 'assistant', content: `Error: ${e.message}` }];
        } finally {
            isStreaming = false;
        }
    }

    async function handleLoad(id: string) {
        const convo = await loadConversation(id);
        messages = convo.messages || [];
        currentModel = convo.model || currentModel;
        currentPersona = convo.persona || null;
    }

    function handleNew() {
        messages = [];
        streamingContent = '';
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }
</script>

<div class="h-screen flex flex-col">
    <TopBar
        {models}
        {personas}
        bind:currentModel
        bind:currentPersona
        bind:currentEffort
    />
    <div class="flex flex-1 overflow-hidden">
        <Sidebar {conversations} onLoad={handleLoad} onNew={handleNew} />
        <div class="flex flex-col flex-1">
            <Chat {messages} {streamingContent} />
            <div class="border-t border-zinc-700 p-4">
                <div class="max-w-3xl mx-auto flex gap-2">
                    <textarea
                        bind:this={inputEl}
                        bind:value={inputText}
                        on:keydown={handleKeydown}
                        placeholder="Type a message..."
                        rows="1"
                        class="flex-1 bg-zinc-800 text-zinc-100 rounded-xl px-4 py-3 text-sm resize-none border border-zinc-600 focus:outline-none focus:border-zinc-400 placeholder-zinc-500"
                        disabled={isStreaming}
                    />
                    <button
                        on:click={sendMessage}
                        disabled={isStreaming || !inputText.trim()}
                        class="bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white px-4 py-2 rounded-xl text-sm transition-colors"
                    >
                        Send
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
```

- [ ] **Step 3: Verify dev server shows the UI**

```bash
cd C:\Users\exvsy\model-chat\web\frontend
npm run dev
```

Open browser to the dev URL. Verify: sidebar on left, top bar with model dropdown, chat area center, input at bottom.

- [ ] **Step 4: Commit**

```bash
cd C:\Users\exvsy\model-chat
git add web/frontend/src/routes/
git commit -m "feat: main page — compose TopBar, Chat, Sidebar into full UI"
```

---

## Task 16: Build Frontend & Verify Full Stack

**Files:**
- Modify: `web/frontend/` (build output)

- [ ] **Step 1: Build the SvelteKit frontend to static files**

```bash
cd C:\Users\exvsy\model-chat\web\frontend
npm run build
```

Expected: Static files output to `web/static/` (as configured in svelte.config.js).

- [ ] **Step 2: Start the FastAPI backend and verify it serves the frontend**

```bash
cd C:\Users\exvsy\model-chat
mchat --web
```

Expected: Browser opens to `http://127.0.0.1:8000`, shows the chat UI.

- [ ] **Step 3: End-to-end test — send a message via the web UI**

1. Select a model from the dropdown
2. Type "hello" and click Send
3. Verify streaming response appears in the chat panel
4. Check the conversation appears in the sidebar after the response completes

- [ ] **Step 4: End-to-end test — verify CLI still works**

```bash
mchat
```

Type `hello`, verify streaming response. Type `/quit`.

- [ ] **Step 5: Commit the built frontend**

```bash
cd C:\Users\exvsy\model-chat
git add web/static/
git commit -m "build: pre-built SvelteKit frontend for static serving"
```

---

## Task 17: Dockerfile & README

**Files:**
- Create: `Dockerfile`
- Create: `README.md`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["mchat", "--web", "--host", "0.0.0.0"]
```

- [ ] **Step 2: Create `README.md`**

```markdown
# model-chat

Chat with any LLM via OpenRouter. CLI and web UI.

## Install

```bash
git clone https://github.com/<user>/model-chat.git
cd model-chat
pip install .
```

Requires Python 3.10+ and an [OpenRouter](https://openrouter.ai) API key:

```bash
export OPENROUTER_API_KEY=sk-or-...
```

On Windows:
```powershell
setx OPENROUTER_API_KEY "sk-or-..."
```

## Usage

**CLI:**
```bash
mchat                                # start chatting
mchat --model gpt-4o --persona coder # with options
```

**Web UI:**
```bash
mchat --web                          # opens browser
```

Type `/help` in the CLI for all commands.

## Docker (optional)

```bash
docker build -t model-chat .
docker run -e OPENROUTER_API_KEY=sk-or-... -p 8000:8000 model-chat
```
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile README.md
git commit -m "docs: README and Dockerfile"
```

---

## Task 18: GitHub Repository

- [ ] **Step 1: Create GitHub repo**

```bash
cd C:\Users\exvsy\model-chat
gh repo create model-chat --public --source . --push
```

(Change `--public` to `--private` if preferred.)

- [ ] **Step 2: Verify repo is live**

```bash
gh repo view --web
```

Expected: Browser opens to the GitHub repo with all code pushed.
