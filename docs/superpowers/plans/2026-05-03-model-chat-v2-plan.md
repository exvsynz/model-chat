# model-chat v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship model-chat v2 with proper licensing, CI, quality hardening, CLI polish (tab completion, usage stats, new commands), and web UI features (auto-titles, delete, themes).

**Architecture:** Four tiers executed sequentially. Tier 1 fixes shipping gaps (LICENSE, CI, server validation). Tier 2 hardens quality (test coverage for untested CLI modules, smoke test). Tier 3 adds CLI polish (completers, /retry, /edit, /copy, /info, usage display, colored prompt). Tier 4 adds web features (auto-titles, delete, /export, theme toggle). Each tier produces independently shippable commits.

**Tech Stack:** Python 3.12, AsyncOpenAI, prompt_toolkit, Rich, FastAPI, SSE, SvelteKit 5, Svelte 5 runes, Tailwind CSS v4, pytest, pytest-asyncio, GitHub Actions

---

## File Structure

### New files
- `LICENSE` — MIT license text
- `.github/workflows/ci.yml` — GitHub Actions CI pipeline
- `cli/completers.py` — prompt_toolkit completers for slash commands, models, personas, file paths
- `core/usage.py` — UsageStats dataclass and format_usage (in core to avoid circular imports)
- `tests/test_app.py` — Tests for cli/app.py (argparse, main entry)
- `tests/test_render.py` — Tests for cli/render.py
- `tests/test_completers.py` — Tests for cli/completers.py
- `tests/test_usage.py` — Tests for core/usage.py

### Modified files
- `core/client.py` — Return usage metadata alongside tokens from stream
- `cli/app.py` — Integrate completers, usage display, colored prompt
- `cli/commands.py` — Add /retry, /edit, /copy, /info, /export commands; update COMMAND_HELP and CommandHandler
- `cli/render.py` — Add print_usage() and print_colored() helpers
- `web/backend/server.py` — Add startup API key check, missing-build warning, DELETE endpoint, title generation endpoint
- `web/frontend/src/lib/api.ts` — Add deleteConversation(), generateTitle() API calls
- `web/frontend/src/lib/Sidebar.svelte` — Add delete button, show auto-generated titles
- `web/frontend/src/lib/TopBar.svelte` — Add theme toggle button
- `web/frontend/src/routes/+page.svelte` — Wire delete handler, auto-title after first response, theme state
- `web/frontend/src/app.css` — Light theme CSS variables
- `web/frontend/src/app.html` — Support theme class toggle

---

## Tier 1: Shipping Gaps

### Task 1: MIT LICENSE File

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Create the LICENSE file**

```text
MIT License

Copyright (c) 2026 model-chat contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Commit**

```bash
git add LICENSE
git commit -m "chore: add MIT LICENSE file"
```

---

### Task 2: Server Startup Validation

**Files:**
- Modify: `web/backend/server.py:36-106`

- [ ] **Step 1: Write the failing test for API key warning**

Add to `tests/test_server.py`:

```python
import logging

def test_server_logs_warning_when_no_api_key(app, caplog):
    """Server should log a warning on startup if OPENROUTER_API_KEY is not set."""
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {}, clear=True):
        with caplog.at_level(logging.WARNING):
            from web.backend.server import create_app
            test_app = create_app()
    assert any("OPENROUTER_API_KEY" in r.message for r in caplog.records)


def test_server_logs_warning_when_no_static_build(app, caplog):
    """Server should log a warning if the frontend static build directory is missing."""
    from unittest.mock import patch, PropertyMock
    from pathlib import Path
    with caplog.at_level(logging.WARNING):
        with patch.object(Path, 'exists', return_value=False):
            from web.backend.server import create_app
            test_app = create_app()
    assert any("static" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server.py::test_server_logs_warning_when_no_api_key tests/test_server.py::test_server_logs_warning_when_no_static_build -v`
Expected: FAIL — no warning is logged

- [ ] **Step 3: Add startup validation to server.py**

At the top of `web/backend/server.py`, add the import:

```python
import logging
import os

logger = logging.getLogger("model-chat")
```

Inside `create_app()`, right after `app = FastAPI(title="model-chat")` and before the middleware, add:

```python
    if not os.environ.get("OPENROUTER_API_KEY"):
        logger.warning("OPENROUTER_API_KEY is not set — /api/chat will fail")
```

Replace the static mount block at the bottom of `create_app()` (lines 102-104) with:

```python
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    else:
        logger.warning(f"Frontend static build not found at {static_dir} — web UI will not be served")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add web/backend/server.py tests/test_server.py
git commit -m "feat: log warnings on missing API key and static build at server startup"
```

---

### Task 3: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the CI workflow**

```yaml
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run tests
        run: pytest tests/ -v
        env:
          OPENROUTER_API_KEY: "sk-or-test-dummy"

  frontend-check:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web/frontend
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: web/frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Type check
        run: npm run check

      - name: Build
        run: npm run build

  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install
        run: pip install .

      - name: Verify import
        run: python -c "from core.client import chat_stream; from cli.app import main; print('OK')"

      - name: Verify CLI --help
        run: mchat --help
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow for pytest, frontend type-check, and smoke test"
```

---

## Tier 2: Quality Hardening

### Task 4: Test cli/render.py

**Files:**
- Create: `tests/test_render.py`

- [ ] **Step 1: Write the tests**

```python
from unittest.mock import patch
from cli.render import print_markdown, print_streaming_token, print_streaming_end, print_info, print_error, print_success


def test_print_info(capsys):
    print_info("hello")
    assert capsys.readouterr().out == "hello\n"


def test_print_error(capsys):
    print_error("bad thing")
    assert capsys.readouterr().out == "Error: bad thing\n"


def test_print_success(capsys):
    print_success("done")
    assert capsys.readouterr().out == "done\n"


def test_print_streaming_token(capsys):
    print_streaming_token("tok")
    captured = capsys.readouterr()
    assert captured.out == "tok"


def test_print_streaming_end(capsys):
    print_streaming_end()
    captured = capsys.readouterr()
    assert captured.out == "\n"


def test_print_markdown():
    with patch("cli.render._console") as mock_console:
        print_markdown("# Hello")
        mock_console.print.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_render.py -v`
Expected: All 6 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_render.py
git commit -m "test: add tests for cli/render.py"
```

---

### Task 5: Test cli/app.py (argparse and entry point)

**Files:**
- Create: `tests/test_app.py`

- [ ] **Step 1: Write the tests**

```python
import pytest
from unittest.mock import patch, MagicMock


def test_main_parses_default_args():
    """main() with no args starts the REPL."""
    with patch("cli.app.asyncio") as mock_asyncio, \
         patch("cli.app.ModelRegistry") as mock_mr, \
         patch("cli.app.PersonaStore") as mock_ps, \
         patch("cli.app.ConversationStore"):
        mock_mr.from_bundled.return_value = MagicMock(default="test/model")
        mock_ps.from_bundled.return_value = MagicMock()

        import sys
        with patch.object(sys, "argv", ["mchat"]):
            from cli.app import main
            main()

        mock_asyncio.run.assert_called_once()


def test_main_web_launches_uvicorn():
    """main() with --web starts uvicorn instead of REPL."""
    with patch("cli.app.uvicorn") as mock_uvicorn, \
         patch("cli.app.webbrowser"), \
         patch("web.backend.server.create_app") as mock_create_app:
        mock_create_app.return_value = MagicMock()

        import sys
        with patch.object(sys, "argv", ["mchat", "--web"]):
            from cli.app import main
            main()

        mock_uvicorn.run.assert_called_once()
        call_kwargs = mock_uvicorn.run.call_args
        assert call_kwargs.kwargs["host"] == "127.0.0.1"
        assert call_kwargs.kwargs["port"] == 8000


def test_main_web_custom_host_port():
    """main() with --web --host --port passes them through."""
    with patch("cli.app.uvicorn") as mock_uvicorn, \
         patch("cli.app.webbrowser"), \
         patch("web.backend.server.create_app") as mock_create_app:
        mock_create_app.return_value = MagicMock()

        import sys
        with patch.object(sys, "argv", ["mchat", "--web", "--host", "0.0.0.0", "--port", "3000"]):
            from cli.app import main
            main()

        call_kwargs = mock_uvicorn.run.call_args
        assert call_kwargs.kwargs["host"] == "0.0.0.0"
        assert call_kwargs.kwargs["port"] == 3000


def test_main_model_arg_resolves():
    """main() with --model resolves the alias via ModelRegistry."""
    with patch("cli.app.asyncio") as mock_asyncio, \
         patch("cli.app.ModelRegistry") as mock_mr, \
         patch("cli.app.PersonaStore") as mock_ps, \
         patch("cli.app.ConversationStore"), \
         patch("cli.app.CommandHandler") as mock_ch:
        mock_registry = MagicMock(default="test/model")
        mock_registry.resolve.return_value = "deepseek/deepseek-r1"
        mock_mr.from_bundled.return_value = mock_registry
        mock_ps.from_bundled.return_value = MagicMock()
        mock_handler = MagicMock()
        mock_ch.return_value = mock_handler

        import sys
        with patch.object(sys, "argv", ["mchat", "--model", "deepseek-r1"]):
            from cli.app import main
            main()

        mock_registry.resolve.assert_called_with("deepseek-r1")
        assert mock_handler.current_model == "deepseek/deepseek-r1"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_app.py -v`
Expected: All 4 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_app.py
git commit -m "test: add tests for cli/app.py entry point and argparse"
```

---

## Tier 3: CLI Polish

### Task 6: Token Usage and Response Time Tracking

**Files:**
- Create: `core/usage.py`
- Create: `tests/test_usage.py`
- Modify: `core/client.py:17-41`
- Modify: `cli/app.py:37-61`
- Modify: `cli/render.py`

The current `chat_stream()` only yields string tokens. OpenRouter returns a final chunk with `usage` data (prompt_tokens, completion_tokens, total_tokens). We need to capture that and the elapsed time.

- [ ] **Step 1: Write the failing test for usage.py**

Create `tests/test_usage.py`:

```python
from core.usage import UsageStats, format_usage


def test_usage_stats_format():
    stats = UsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150, elapsed_seconds=2.5)
    text = format_usage(stats)
    assert "150 tokens" in text
    assert "2.5s" in text


def test_usage_stats_format_no_tokens():
    stats = UsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0, elapsed_seconds=1.0)
    text = format_usage(stats)
    assert "1.0s" in text


def test_usage_stats_format_with_model():
    stats = UsageStats(prompt_tokens=10, completion_tokens=20, total_tokens=30, elapsed_seconds=0.8)
    text = format_usage(stats, model="deepseek/deepseek-v4-flash")
    assert "deepseek-v4-flash" in text
    assert "30 tokens" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_usage.py -v`
Expected: FAIL — `core.usage` module not found

- [ ] **Step 3: Create core/usage.py**

```python
from dataclasses import dataclass


@dataclass
class UsageStats:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    elapsed_seconds: float


def format_usage(stats: UsageStats, model: str | None = None) -> str:
    parts = []
    if model:
        short = model.split("/")[-1] if "/" in model else model
        parts.append(short)
    if stats.total_tokens > 0:
        parts.append(f"{stats.total_tokens} tokens ({stats.prompt_tokens}+{stats.completion_tokens})")
    parts.append(f"{stats.elapsed_seconds:.1f}s")
    return " · ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_usage.py -v`
Expected: All 3 PASS

- [ ] **Step 5: Modify core/client.py to yield a usage sentinel at end of stream**

The stream currently yields `str` tokens. After the stream ends, we need to return usage info. Change the return type to yield either strings or a `UsageStats` object as the final item.

Replace the `chat_stream` function in `core/client.py` with:

```python
import time
from core.usage import UsageStats


async def chat_stream(
    messages: list[dict],
    model: str,
    system_prompt: str | None = None,
    effort: str | None = None,
) -> AsyncGenerator[str | UsageStats, None]:
    client = get_async_openai_client()

    final_messages = []
    if system_prompt:
        final_messages.append({"role": "system", "content": system_prompt})
    final_messages.extend(messages)

    kwargs: dict = {
        "model": model,
        "messages": final_messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if effort:
        kwargs["extra_body"] = {"reasoning_effort": effort}

    start = time.monotonic()
    stream = await client.chat.completions.create(**kwargs)
    usage_data = None
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
        if hasattr(chunk, "usage") and chunk.usage:
            usage_data = chunk.usage

    elapsed = time.monotonic() - start
    prompt_tokens = getattr(usage_data, "prompt_tokens", 0) if usage_data else 0
    completion_tokens = getattr(usage_data, "completion_tokens", 0) if usage_data else 0
    yield UsageStats(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        elapsed_seconds=round(elapsed, 1),
    )
```

- [ ] **Step 6: Add print_usage to cli/render.py**

Append to `cli/render.py`:

```python
def print_usage(text: str) -> None:
    print(f"\033[90m{text}\033[0m")
```

- [ ] **Step 7: Update cli/app.py run_chat to display usage**

Replace the `run_chat` function in `cli/app.py`:

```python
from core.usage import UsageStats, format_usage
from cli.render import (
    print_markdown,
    print_streaming_token,
    print_streaming_end,
    print_info,
    print_error,
    print_usage,
)


async def run_chat(handler: CommandHandler, user_input: str) -> None:
    handler.messages.append({"role": "user", "content": user_input})

    full_response = ""
    usage: UsageStats | None = None
    try:
        async for item in chat_stream(
            messages=handler.messages,
            model=handler.current_model,
            system_prompt=handler.system_prompt,
            effort=handler.effort,
        ):
            if isinstance(item, UsageStats):
                usage = item
            else:
                print_streaming_token(item)
                full_response += item
        print_streaming_end()
        if usage:
            print_usage(format_usage(usage, model=handler.current_model))
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
    handler.last_response = full_response
```

- [ ] **Step 8: Update existing client tests to account for UsageStats yield**

In `tests/test_client.py`, update `test_chat_stream_yields_tokens`:

```python
from core.usage import UsageStats


@pytest.mark.asyncio
async def test_chat_stream_yields_tokens():
    mock_chunk_1 = MagicMock()
    mock_chunk_1.choices = [MagicMock()]
    mock_chunk_1.choices[0].delta.content = "Hello"
    mock_chunk_1.usage = None

    mock_chunk_2 = MagicMock()
    mock_chunk_2.choices = [MagicMock()]
    mock_chunk_2.choices[0].delta.content = " world"
    mock_chunk_2.usage = None

    mock_chunk_3 = MagicMock()
    mock_chunk_3.choices = [MagicMock()]
    mock_chunk_3.choices[0].delta.content = None
    mock_chunk_3.usage = None

    async def mock_stream():
        for chunk in [mock_chunk_1, mock_chunk_2, mock_chunk_3]:
            yield chunk

    with patch("core.client.get_async_openai_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_get_client.return_value = mock_client

        items = []
        async for item in chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/gpt-4o",
        ):
            items.append(item)

    tokens = [i for i in items if isinstance(i, str)]
    usage_items = [i for i in items if isinstance(i, UsageStats)]
    assert tokens == ["Hello", " world"]
    assert len(usage_items) == 1
```

Update the other two tests (`test_chat_stream_with_system_prompt`, `test_chat_stream_with_effort`) similarly — add `mock_chunk.usage = None` to each mock chunk, and collect items filtering by type. The system prompt and effort assertions remain the same.

- [ ] **Step 9: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
git add core/usage.py tests/test_usage.py core/client.py cli/render.py cli/app.py tests/test_client.py
git commit -m "feat: display token usage and response time after each response"
```

---

### Task 7: /info Command

**Files:**
- Modify: `cli/commands.py:18-33` (COMMAND_HELP)
- Modify: `cli/commands.py` (CommandHandler)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_commands.py`:

```python
from cli.commands import CommandHandler
from core.models import ModelRegistry
from core.personas import PersonaStore
from core.store import ConversationStore
from pathlib import Path
import tempfile


@pytest.fixture
def handler(tmp_path):
    config_path = Path(__file__).parent.parent / "config" / "models.yaml"
    models = ModelRegistry(config_path)
    personas_dir = Path(__file__).parent.parent / "config" / "personas"
    personas = PersonaStore(personas_dir)
    store = ConversationStore(tmp_path / "convos")
    return CommandHandler(models=models, personas=personas, store=store)


def test_cmd_info_shows_current_state(handler, capsys):
    handler.current_model = "deepseek/deepseek-v4-flash"
    handler.persona_name = "coder"
    handler.effort = "high"
    handler.messages = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    handler.handle("info", "")
    output = capsys.readouterr().out
    assert "deepseek-v4-flash" in output
    assert "coder" in output
    assert "high" in output
    assert "2" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_commands.py::test_cmd_info_shows_current_state -v`
Expected: FAIL — Unknown command: /info

- [ ] **Step 3: Add /info to COMMAND_HELP and implement**

In `cli/commands.py`, add to `COMMAND_HELP` dict (before "help"):

```python
    "info": ("/info", "Show current session state"),
```

Add the handler method to `CommandHandler`:

```python
    def _cmd_info(self, args: str) -> str | None:
        model = self.current_model
        model_short = model.split("/")[-1] if "/" in model else model
        persona = self.persona_name or "(none)"
        effort = self.effort or "(default)"
        msg_count = len(self.messages)
        print_info(f"  Model:    {model_short} ({model})")
        print_info(f"  Persona:  {persona}")
        print_info(f"  Effort:   {effort}")
        print_info(f"  Messages: {msg_count}")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_commands.py::test_cmd_info_shows_current_state -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cli/commands.py tests/test_commands.py
git commit -m "feat: add /info command to show current session state"
```

---

### Task 8: /retry Command

**Files:**
- Modify: `cli/commands.py`
- Modify: `cli/app.py:64-96`

The /retry command removes the last assistant message and re-sends the last user message. Since `chat_stream` is async and `CommandHandler.handle()` is sync, /retry needs to signal the REPL to re-run chat. We return a special signal string.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_commands.py`:

```python
def test_cmd_retry_returns_signal(handler):
    handler.messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    result = handler.handle("retry", "")
    assert result == "retry"
    assert len(handler.messages) == 1
    assert handler.messages[0]["role"] == "user"


def test_cmd_retry_empty_history(handler, capsys):
    handler.messages = []
    result = handler.handle("retry", "")
    assert result is None
    assert "No messages" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_commands.py::test_cmd_retry_returns_signal tests/test_commands.py::test_cmd_retry_empty_history -v`
Expected: FAIL

- [ ] **Step 3: Add /retry to COMMAND_HELP and implement**

In `cli/commands.py`, add to `COMMAND_HELP`:

```python
    "retry": ("/retry", "Regenerate last response"),
```

Add the handler method:

```python
    def _cmd_retry(self, args: str) -> str | None:
        if not self.messages:
            print_error("No messages to retry")
            return None
        if self.messages[-1]["role"] == "assistant":
            self.messages.pop()
        if not self.messages or self.messages[-1]["role"] != "user":
            print_error("No user message to retry")
            return None
        return "retry"
```

- [ ] **Step 4: Handle the "retry" signal in cli/app.py repl()**

In the `repl()` function in `cli/app.py`, update the command handling block (around line 88-94):

```python
        cmd, args = parse_command(user_input)
        if cmd is not None:
            result = handler.handle(cmd, args)
            if result == "quit":
                print_info("Goodbye!")
                break
            if result == "retry":
                last_user_msg = handler.messages[-1]["content"]
                handler.messages.pop()
                await run_chat(handler, last_user_msg)
            continue
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_commands.py::test_cmd_retry_returns_signal tests/test_commands.py::test_cmd_retry_empty_history -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cli/commands.py cli/app.py tests/test_commands.py
git commit -m "feat: add /retry command to regenerate last response"
```

---

### Task 9: /edit Command

**Files:**
- Modify: `cli/commands.py`
- Modify: `cli/app.py`

The /edit command removes the last assistant+user message pair and returns "edit" signal with the original user text for re-editing. The REPL pre-fills the prompt with that text.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_commands.py`:

```python
def test_cmd_edit_returns_signal(handler):
    handler.messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    result = handler.handle("edit", "")
    assert result == "edit"
    assert len(handler.messages) == 0
    assert handler.edit_text == "hello"


def test_cmd_edit_empty_history(handler, capsys):
    handler.messages = []
    result = handler.handle("edit", "")
    assert result is None
    assert "No messages" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_commands.py::test_cmd_edit_returns_signal tests/test_commands.py::test_cmd_edit_empty_history -v`
Expected: FAIL

- [ ] **Step 3: Add /edit to COMMAND_HELP and implement**

In `cli/commands.py`, add to `COMMAND_HELP`:

```python
    "edit": ("/edit", "Edit and re-send last message"),
```

Add `edit_text` attribute to `CommandHandler.__init__`:

```python
        self.edit_text: str | None = None
```

Add the handler method:

```python
    def _cmd_edit(self, args: str) -> str | None:
        if not self.messages:
            print_error("No messages to edit")
            return None
        if self.messages[-1]["role"] == "assistant":
            self.messages.pop()
        if self.messages and self.messages[-1]["role"] == "user":
            self.edit_text = self.messages.pop()["content"]
            return "edit"
        print_error("No user message to edit")
        return None
```

- [ ] **Step 4: Handle "edit" signal in cli/app.py repl()**

Update the command handling block in `repl()`:

```python
        cmd, args = parse_command(user_input)
        if cmd is not None:
            result = handler.handle(cmd, args)
            if result == "quit":
                print_info("Goodbye!")
                break
            if result == "retry":
                last_user_msg = handler.messages[-1]["content"]
                handler.messages.pop()
                await run_chat(handler, last_user_msg)
            if result == "edit":
                edit_input = await session.prompt_async(
                    f"[{model_short}] edit> ",
                    default=handler.edit_text or "",
                )
                edit_input = edit_input.strip()
                if edit_input:
                    await run_chat(handler, edit_input)
                handler.edit_text = None
            continue
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_commands.py::test_cmd_edit_returns_signal tests/test_commands.py::test_cmd_edit_empty_history -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cli/commands.py cli/app.py tests/test_commands.py
git commit -m "feat: add /edit command to edit and re-send last message"
```

---

### Task 10: /copy Command

**Files:**
- Modify: `cli/commands.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_commands.py`:

```python
def test_cmd_copy_copies_last_response(handler, capsys):
    handler.messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    from unittest.mock import patch
    with patch("cli.commands.subprocess") as mock_sp:
        mock_sp.run = MagicMock()
        handler.handle("copy", "")
    output = capsys.readouterr().out
    assert "Copied" in output


def test_cmd_copy_no_response(handler, capsys):
    handler.messages = []
    handler.handle("copy", "")
    assert "No response" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_commands.py::test_cmd_copy_copies_last_response tests/test_commands.py::test_cmd_copy_no_response -v`
Expected: FAIL

- [ ] **Step 3: Add /copy to COMMAND_HELP and implement**

In `cli/commands.py`, add the import at the top:

```python
import subprocess
import sys
```

Add to `COMMAND_HELP`:

```python
    "copy": ("/copy", "Copy last response to clipboard"),
```

Add `last_response` attribute to `CommandHandler.__init__`:

```python
        self.last_response: str | None = None
```

Add the handler method:

```python
    def _cmd_copy(self, args: str) -> str | None:
        if not self.last_response:
            print_error("No response to copy")
            return None
        try:
            if sys.platform == "win32":
                subprocess.run(["clip"], input=self.last_response.encode("utf-8"), check=True)
            elif sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=self.last_response.encode("utf-8"), check=True)
            else:
                subprocess.run(["xclip", "-selection", "clipboard"], input=self.last_response.encode("utf-8"), check=True)
            print_success("Copied to clipboard")
        except Exception as e:
            print_error(f"Failed to copy: {e}")
        return None
```

- [ ] **Step 4: Update run_chat in cli/app.py to set handler.last_response**

This was already done in Task 6 Step 7. Verify that `handler.last_response = full_response` is set at the end of `run_chat()`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_commands.py::test_cmd_copy_copies_last_response tests/test_commands.py::test_cmd_copy_no_response -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cli/commands.py tests/test_commands.py
git commit -m "feat: add /copy command to copy last response to clipboard"
```

---

### Task 11: /export Command

**Files:**
- Modify: `cli/commands.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_commands.py`:

```python
def test_cmd_export_writes_markdown(handler, tmp_path, capsys):
    handler.messages = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language."},
    ]
    handler.current_model = "deepseek/deepseek-v4-flash"
    output_path = str(tmp_path / "export.md")
    handler.handle("export", output_path)
    output = capsys.readouterr().out
    assert "Exported" in output
    content = (tmp_path / "export.md").read_text(encoding="utf-8")
    assert "What is Python?" in content
    assert "Python is a programming language." in content


def test_cmd_export_no_messages(handler, capsys):
    handler.messages = []
    handler.handle("export", "test.md")
    assert "No messages" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_commands.py::test_cmd_export_writes_markdown tests/test_commands.py::test_cmd_export_no_messages -v`
Expected: FAIL

- [ ] **Step 3: Add /export to COMMAND_HELP and implement**

Add to `COMMAND_HELP`:

```python
    "export": ("/export <path>", "Export conversation as markdown"),
```

Add the handler method:

```python
    def _cmd_export(self, args: str) -> str | None:
        if not self.messages:
            print_error("No messages to export")
            return None
        if not args:
            print_error("Usage: /export <path>")
            return None
        path = Path(args).expanduser()
        lines = [f"# Conversation — {self.current_model}\n"]
        for msg in self.messages:
            role = msg["role"].capitalize()
            lines.append(f"## {role}\n")
            lines.append(msg["content"])
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        print_success(f"Exported {len(self.messages)} messages to {path}")
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_commands.py::test_cmd_export_writes_markdown tests/test_commands.py::test_cmd_export_no_messages -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cli/commands.py tests/test_commands.py
git commit -m "feat: add /export command to dump conversation as markdown"
```

---

### Task 12: Smart Tab Completion

**Files:**
- Create: `cli/completers.py`
- Create: `tests/test_completers.py`
- Modify: `cli/app.py:26-34`

prompt_toolkit supports `merge_completers` and custom `Completer` subclasses. We'll create a completer that:
- Completes slash commands when input starts with `/`
- After `/model `, completes model aliases
- After `/persona `, completes persona names
- After `/file `, completes file paths
- After `/load `, completes conversation IDs

- [ ] **Step 1: Write the failing test**

Create `tests/test_completers.py`:

```python
import pytest
from unittest.mock import MagicMock
from prompt_toolkit.document import Document
from prompt_toolkit.completion import CompleteEvent
from cli.completers import ChatCompleter


@pytest.fixture
def completer():
    handler = MagicMock()
    handler.registry.list_commands.return_value = ["model", "persona", "help", "quit", "file", "load"]
    handler.models.list_aliases.return_value = [("deepseek-r1", "deepseek/deepseek-r1"), ("gpt-4o", "openai/gpt-4o")]
    handler.personas.list_names.return_value = ["coder", "tutor", "general"]
    handler.store.list_all.return_value = [{"id": "2026-05-01_chat1"}, {"id": "2026-05-02_chat2"}]
    return ChatCompleter(handler)


def test_completes_slash_commands(completer):
    doc = Document("/mo")
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    texts = [c.text for c in completions]
    assert "/model" in texts


def test_completes_model_names(completer):
    doc = Document("/model dee")
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    texts = [c.text for c in completions]
    assert "deepseek-r1" in texts


def test_completes_persona_names(completer):
    doc = Document("/persona co")
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    texts = [c.text for c in completions]
    assert "coder" in texts


def test_completes_load_ids(completer):
    doc = Document("/load 2026")
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    texts = [c.text for c in completions]
    assert "2026-05-01_chat1" in texts
    assert "2026-05-02_chat2" in texts


def test_no_completions_for_regular_text(completer):
    doc = Document("hello world")
    event = CompleteEvent()
    completions = list(completer.get_completions(doc, event))
    assert len(completions) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_completers.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create cli/completers.py**

```python
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class ChatCompleter(Completer):
    def __init__(self, handler):
        self._handler = handler

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor

        if not text.startswith("/"):
            return

        parts = text.split(None, 1)
        cmd_part = parts[0]

        if len(parts) == 1 and not text.endswith(" "):
            commands = ["/" + c for c in self._handler.registry.list_commands()]
            for cmd in commands:
                if cmd.startswith(cmd_part):
                    yield Completion(cmd, start_position=-len(cmd_part))
            return

        if len(parts) < 2:
            arg_text = ""
        else:
            arg_text = parts[1]

        cmd_name = cmd_part[1:]

        if cmd_name == "model":
            aliases = self._handler.models.list_aliases()
            for alias, _ in aliases:
                if alias.startswith(arg_text):
                    yield Completion(alias, start_position=-len(arg_text))

        elif cmd_name == "persona":
            names = self._handler.personas.list_names()
            for name in names:
                if name.startswith(arg_text):
                    yield Completion(name, start_position=-len(arg_text))

        elif cmd_name == "load":
            summaries = self._handler.store.list_all()
            for s in summaries:
                convo_id = s["id"]
                if convo_id.startswith(arg_text):
                    yield Completion(convo_id, start_position=-len(arg_text))

        elif cmd_name == "file":
            from pathlib import Path
            prefix = Path(arg_text) if arg_text else Path(".")
            parent = prefix.parent if arg_text and not arg_text.endswith("/") else prefix
            stem = prefix.name if arg_text and not arg_text.endswith("/") else ""
            try:
                for p in parent.iterdir():
                    name = str(p)
                    if name.startswith(arg_text) or p.name.startswith(stem):
                        yield Completion(str(p), start_position=-len(arg_text))
            except OSError:
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_completers.py -v`
Expected: All 5 PASS

- [ ] **Step 5: Integrate ChatCompleter into cli/app.py**

Replace the `get_prompt_session` function in `cli/app.py`:

```python
from cli.completers import ChatCompleter


def get_prompt_session(handler: CommandHandler) -> PromptSession:
    completer = ChatCompleter(handler)
    history_path = DATA_DIR / "history"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    return PromptSession(
        completer=completer,
        history=FileHistory(str(history_path)),
    )
```

Remove the now-unused `WordCompleter` import from the top of `cli/app.py`.

- [ ] **Step 6: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add cli/completers.py tests/test_completers.py cli/app.py
git commit -m "feat: smart tab completion for commands, models, personas, files, and conversation IDs"
```

---

### Task 13: Colored Prompt

**Files:**
- Modify: `cli/app.py:64-96`

prompt_toolkit supports ANSI-formatted prompts via `FormattedText` or HTML. We'll use a simple ANSI-styled prompt to distinguish the model name.

- [ ] **Step 1: Update the prompt in repl()**

In `cli/app.py`, add the import:

```python
from prompt_toolkit.formatted_text import HTML
```

Replace the prompt strings in the `repl()` function. Change:

```python
                user_input = await session.prompt_async(
                    f"[{model_short}] > ",
                    multiline=True,
                )
```

to:

```python
                user_input = await session.prompt_async(
                    HTML(f"<aaa fg='ansicyan'>[{model_short}]</aaa> &gt; "),
                    multiline=True,
                )
```

And change the non-multiline prompt:

```python
                user_input = await session.prompt_async(f"[{model_short}] > ")
```

to:

```python
                user_input = await session.prompt_async(
                    HTML(f"<aaa fg='ansicyan'>[{model_short}]</aaa> &gt; ")
                )
```

Also update the edit prompt (added in Task 9):

```python
                edit_input = await session.prompt_async(
                    HTML(f"<aaa fg='ansiyellow'>[{model_short}] edit</aaa> &gt; "),
                    default=handler.edit_text or "",
                )
```

- [ ] **Step 2: Run all tests to ensure no regressions**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add cli/app.py
git commit -m "feat: colored CLI prompt showing model name in cyan"
```

---

## Tier 4: Web UI Features

### Task 14: Conversation Delete (Backend)

**Files:**
- Modify: `web/backend/server.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_delete_conversation_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete("/api/conversations/nonexistent")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py::test_delete_conversation_not_found -v`
Expected: FAIL — 405 Method Not Allowed (no DELETE route)

- [ ] **Step 3: Add DELETE endpoint to server.py**

In `create_app()` in `web/backend/server.py`, add after the `get_conversation` endpoint:

```python
    @app.delete("/api/conversations/{convo_id}")
    def delete_conversation(convo_id: str):
        convo = store.load(convo_id)
        if convo is None:
            raise HTTPException(status_code=404, detail="not found")
        store.delete(convo_id)
        return {"status": "deleted", "id": convo_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add web/backend/server.py tests/test_server.py
git commit -m "feat: add DELETE /api/conversations/{id} endpoint"
```

---

### Task 15: Conversation Delete (Frontend)

**Files:**
- Modify: `web/frontend/src/lib/api.ts`
- Modify: `web/frontend/src/lib/Sidebar.svelte`
- Modify: `web/frontend/src/routes/+page.svelte`

- [ ] **Step 1: Add deleteConversation to api.ts**

Append to `web/frontend/src/lib/api.ts`:

```typescript
export async function deleteConversation(id: string): Promise<void> {
    await fetch(`${BASE}/api/conversations/${id}`, { method: 'DELETE' });
}
```

- [ ] **Step 2: Add delete button to Sidebar.svelte**

Replace the conversation button in `Sidebar.svelte`:

```svelte
<script lang="ts">
    import type { ConversationSummary } from './api';

    let {
        conversations = [],
        onLoad,
        onNew,
        onDelete,
    }: {
        conversations?: ConversationSummary[];
        onLoad: (id: string) => void;
        onNew: () => void;
        onDelete: (id: string) => void;
    } = $props();
</script>

<div class="w-64 border-r border-zinc-700 flex flex-col h-full" style="background-color: rgb(20 20 20);">
    <div class="p-3">
        <button
            onclick={onNew}
            class="w-full bg-zinc-700 hover:bg-zinc-600 text-zinc-100 text-sm rounded-lg px-3 py-2 transition-colors"
        >
            + New Chat
        </button>
    </div>

    <div class="flex-1 overflow-y-auto px-2 space-y-1">
        {#each conversations as convo}
            <div class="group flex items-center rounded-lg hover:bg-zinc-700 transition-colors">
                <button
                    onclick={() => onLoad(convo.id)}
                    class="flex-1 text-left px-3 py-2 text-sm text-zinc-300 truncate"
                    title={convo.id}
                >
                    <div class="truncate">{convo.title || convo.id}</div>
                    <div class="text-xs text-zinc-500">{convo.model.split('/').pop()} · {convo.message_count} msgs</div>
                </button>
                <button
                    onclick={(e) => { e.stopPropagation(); onDelete(convo.id); }}
                    class="hidden group-hover:block px-2 text-zinc-500 hover:text-red-400 text-xs"
                    title="Delete"
                >
                    ✕
                </button>
            </div>
        {/each}

        {#if conversations.length === 0}
            <p class="text-xs text-zinc-500 px-3 py-2">No saved conversations</p>
        {/if}
    </div>
</div>
```

- [ ] **Step 3: Wire onDelete in +page.svelte**

Add the import for `deleteConversation` in `+page.svelte`:

```typescript
import {
    // ... existing imports ...
    deleteConversation,
} from '$lib/api';
```

Add the delete handler function:

```typescript
    async function handleDelete(id: string) {
        await deleteConversation(id);
        conversations = await fetchConversations();
    }
```

Update the Sidebar usage:

```svelte
        <Sidebar {conversations} onLoad={handleLoad} onNew={handleNew} onDelete={handleDelete} />
```

- [ ] **Step 4: Build the frontend**

Run from `web/frontend/`:
```bash
npm run build
```

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/lib/api.ts web/frontend/src/lib/Sidebar.svelte web/frontend/src/routes/+page.svelte web/static/
git commit -m "feat: delete conversations from web sidebar"
```

---

### Task 16: Conversation Auto-Title

**Files:**
- Modify: `core/store.py`
- Modify: `web/backend/server.py`
- Modify: `web/frontend/src/lib/api.ts`
- Modify: `web/frontend/src/routes/+page.svelte`

Auto-generate a short title from the first user message. No LLM call needed — just truncate the first user message to 50 chars.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_store.py`:

```python
def test_save_and_load_with_title(tmp_path):
    store = ConversationStore(tmp_path)
    convo = {
        "id": "test-title",
        "model": "test",
        "persona": "",
        "title": "My first chat",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "messages": [],
    }
    store.save(convo)
    loaded = store.load("test-title")
    assert loaded["title"] == "My first chat"
```

- [ ] **Step 2: Run test — it should already pass**

Run: `pytest tests/test_store.py::test_save_and_load_with_title -v`
Expected: PASS (store already saves/loads arbitrary dict fields)

- [ ] **Step 3: Update store.list_all to include title in summaries**

In `core/store.py`, update the `list_all` method to include `title`:

```python
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
                "title": data.get("title", ""),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": len(data.get("messages", [])),
            })
        return summaries
```

- [ ] **Step 4: Update SaveRequest in server.py to include title**

In `web/backend/server.py`, update the `SaveRequest` model:

```python
class SaveRequest(BaseModel):
    id: str
    model: str
    persona: str | None = None
    title: str | None = None
    created_at: str
    updated_at: str
    messages: list[dict]
```

- [ ] **Step 5: Update ConversationSummary in api.ts**

In `web/frontend/src/lib/api.ts`, update the interface:

```typescript
export interface ConversationSummary {
    id: string;
    model: string;
    persona: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}
```

- [ ] **Step 6: Update saveConversation in api.ts**

```typescript
export async function saveConversation(convo: {
    id: string;
    model: string;
    persona: string | null;
    title: string | null;
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
```

- [ ] **Step 7: Generate title in +page.svelte sendMessage()**

In `+page.svelte`, update the save logic inside `sendMessage()` to generate a title from the first user message:

```typescript
            const firstUserMsg = messages.find(m => m.role === 'user');
            const title = firstUserMsg
                ? firstUserMsg.content.slice(0, 50) + (firstUserMsg.content.length > 50 ? '...' : '')
                : 'New conversation';

            const now = new Date().toISOString();
            const modelShort = currentModel.includes('/') ? currentModel.split('/').pop() : currentModel;
            const id = `${now.slice(0, 19).replace(/[T:]/g, '-')}_${modelShort}`;
            await saveConversation({
                id,
                model: currentModel,
                persona: currentPersona,
                title,
                created_at: now,
                updated_at: now,
                messages,
            });
```

- [ ] **Step 8: Build the frontend**

Run from `web/frontend/`:
```bash
npm run build
```

- [ ] **Step 9: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
git add core/store.py web/backend/server.py web/frontend/src/lib/api.ts web/frontend/src/routes/+page.svelte web/static/
git commit -m "feat: auto-generate conversation titles from first user message"
```

---

### Task 17: Dark/Light Theme Toggle

**Files:**
- Modify: `web/frontend/src/app.css`
- Modify: `web/frontend/src/app.html`
- Modify: `web/frontend/src/lib/TopBar.svelte`
- Modify: `web/frontend/src/routes/+page.svelte`

We'll use Tailwind's `dark:` variant with a class toggle on `<html>`. Theme preference is stored in localStorage.

- [ ] **Step 1: Update app.css with light theme defaults**

Replace `web/frontend/src/app.css`:

```css
@import 'tailwindcss';

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

:root {
    color-scheme: light;
}

.dark {
    color-scheme: dark;
}

body {
    @apply bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100;
}

pre code {
    @apply text-sm;
}
```

- [ ] **Step 2: Update app.html to support theme class**

Replace `web/frontend/src/app.html`:

```html
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>model-chat</title>
    <script>
        if (localStorage.getItem('theme') === 'dark' || (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
        }
    </script>
    %sveltekit.head%
</head>
<body>
    <div style="display: contents">%sveltekit.body%</div>
</body>
</html>
```

- [ ] **Step 3: Add theme toggle to TopBar.svelte**

Add a theme toggle button at the end of the TopBar's flex container. Add this state and function at the top of the script:

```typescript
    let isDark = $state(document.documentElement.classList.contains('dark'));

    function toggleTheme() {
        isDark = !isDark;
        document.documentElement.classList.toggle('dark', isDark);
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    }
```

Add the button at the end of the TopBar `<div>`, after the persona `<select>`:

```svelte
    <button
        onclick={toggleTheme}
        class="ml-auto px-2 py-1 text-sm rounded bg-zinc-700 dark:bg-zinc-700 text-zinc-300 hover:bg-zinc-600"
        title="Toggle theme"
    >
        {isDark ? '☀' : '●'}
    </button>
```

- [ ] **Step 4: Update all Svelte components to use dark: variants**

Update `TopBar.svelte` main container class:

```svelte
<div class="flex items-center gap-4 px-4 py-2 bg-zinc-100 dark:bg-zinc-800 border-b border-zinc-300 dark:border-zinc-700">
```

Update all `bg-zinc-700` to include light counterparts: `bg-zinc-200 dark:bg-zinc-700`, all `text-zinc-100` to `text-zinc-900 dark:text-zinc-100`, all `border-zinc-600` to `border-zinc-300 dark:border-zinc-600`.

Update `Sidebar.svelte`:
- Container: `bg-zinc-50 dark:bg-[rgb(20,20,20)]` and `border-zinc-300 dark:border-zinc-700`
- Button: `bg-zinc-200 dark:bg-zinc-700 hover:bg-zinc-300 dark:hover:bg-zinc-600 text-zinc-900 dark:text-zinc-100`

Update `Chat.svelte`:
- User bubble: `bg-zinc-200 dark:bg-zinc-700`
- Prose: `prose dark:prose-invert`

Update `+page.svelte`:
- Input border: `border-zinc-300 dark:border-zinc-700`
- Textarea: `bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border-zinc-300 dark:border-zinc-600`

- [ ] **Step 5: Build the frontend**

Run from `web/frontend/`:
```bash
npm run build
```

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/app.css web/frontend/src/app.html web/frontend/src/lib/TopBar.svelte web/frontend/src/lib/Chat.svelte web/frontend/src/lib/Sidebar.svelte web/frontend/src/routes/+page.svelte web/static/
git commit -m "feat: dark/light theme toggle with localStorage persistence"
```

---

### Task 18: Update COMMAND_HELP Registry and Tests

**Files:**
- Modify: `tests/test_commands.py`

After adding all new commands (info, retry, edit, copy, export), the registry test needs updating.

- [ ] **Step 1: Update the registry test**

In `tests/test_commands.py`, update `test_registry_has_builtin_commands`:

```python
def test_registry_has_builtin_commands(registry):
    names = registry.list_commands()
    assert "model" in names
    assert "models" in names
    assert "browse" in names
    assert "effort" in names
    assert "file" in names
    assert "persona" in names
    assert "personas" in names
    assert "save" in names
    assert "load" in names
    assert "list" in names
    assert "clear" in names
    assert "multi" in names
    assert "info" in names
    assert "retry" in names
    assert "edit" in names
    assert "copy" in names
    assert "export" in names
    assert "help" in names
    assert "quit" in names
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_commands.py
git commit -m "test: update registry test for all new commands"
```

---

### Task 19: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the CLI commands table in README.md**

Add the new commands to the table:

```markdown
| `/info` | Show current session state |
| `/retry` | Regenerate last response |
| `/edit` | Edit and re-send last message |
| `/copy` | Copy last response to clipboard |
| `/export <path>` | Export conversation as markdown |
```

Add a "Features" bullet:
```markdown
- **Token usage**: Displays token count and response time after each message
- **Smart completion**: Tab-complete commands, model names, personas, file paths
- **Theme toggle**: Switch between dark and light mode in the web UI
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with all new commands and features"
```

---

### Task 20: Final Verification

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 2: Run smoke test**

```bash
python -c "from core.client import chat_stream; from cli.app import main; print('OK')"
mchat --help
```
Expected: "OK" and help text

- [ ] **Step 3: Verify frontend type-checks**

From `web/frontend/`:
```bash
npm run check
```
Expected: No errors

- [ ] **Step 4: Build frontend**

From `web/frontend/`:
```bash
npm run build
```
Expected: Success, files in `web/static/`

- [ ] **Step 5: Manual smoke test**

```bash
mchat --model deepseek-v4-flash
```
- Type a message, verify token usage appears after response
- Try `/info`, `/retry`, `/copy`, `/export test.md`
- Try tab completion on `/model ` and `/persona `
- Try `mchat --web` and verify theme toggle works
- Verify delete button appears on hover in sidebar

- [ ] **Step 6: Commit any final fixes and push**

```bash
git push
```
