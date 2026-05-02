# Model Chat — Design Spec

A personal chat client powered by OpenRouter that lets you converse with any LLM through a browser-based web UI or an interactive terminal CLI.

## Goals

- Chat with any model available on OpenRouter
- Switch models instantly mid-conversation
- Web UI that feels like Claude Desktop / ChatGPT
- CLI REPL that feels like Claude Code
- Portable: pip install on any machine and go
- Conversation persistence to JSON files

## Non-Goals (v1)

- Tool use / code execution / agents
- Image or file upload in web UI
- Multi-user / authentication
- Conversation branching or editing past messages
- Token counting or cost tracking

## Architecture

Monorepo with three packages:

```
model-chat/
├── core/               # Python — shared OpenRouter client, conversation store, model registry
│   ├── __init__.py
│   ├── client.py       # OpenRouter streaming client
│   ├── models.py       # Model registry (YAML config + lookup)
│   ├── store.py        # Conversation save/load (JSON)
│   └── personas.py     # System prompt templates
├── cli/                # Python — prompt_toolkit REPL
│   ├── __init__.py
│   ├── app.py          # REPL loop, input handling
│   ├── commands.py     # Slash command registry and handlers
│   └── render.py       # Rich markdown/syntax rendering
├── web/                # SvelteKit frontend + FastAPI backend
│   ├── backend/
│   │   ├── __init__.py
│   │   └── server.py   # FastAPI app, SSE streaming
│   └── frontend/       # SvelteKit app
│       ├── src/
│       │   ├── routes/
│       │   │   └── +page.svelte   # Main chat page
│       │   └── lib/
│       │       ├── Chat.svelte     # Chat panel component
│       │       ├── Sidebar.svelte  # Conversation history sidebar
│       │       ├── TopBar.svelte   # Model dropdown + effort toggle
│       │       └── api.ts          # API client helpers
│       ├── static/
│       ├── package.json
│       └── svelte.config.js
├── config/
│   └── models.yaml     # Default model registry
├── pyproject.toml      # Python packaging, CLI entry points
├── Dockerfile          # Optional containerized deploy
└── README.md
```

## Core Library

### OpenRouter Client (`core/client.py`)

Wraps the OpenAI SDK configured for OpenRouter. Single primary function:

```python
async def chat_stream(
    messages: list[dict],
    model: str,
    system_prompt: str | None = None,
    effort: str | None = None,  # "low", "medium", "high"
) -> AsyncGenerator[str, None]:
    """Stream chat completion tokens from OpenRouter."""
```

- Uses `OPENROUTER_API_KEY` from environment
- Maps `effort` to `reasoning_effort` in extra body params
- Yields string tokens as they arrive
- Raises clear errors for auth failures, invalid models, rate limits

### Model Registry (`core/models.py`)

A YAML config file (`config/models.yaml`) mapping short aliases to full OpenRouter model IDs:

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

The registry resolves aliases but also accepts any raw OpenRouter model ID passed directly.

### Conversation Store (`core/store.py`)

Saves conversations as JSON to `~/.model-chat/conversations/`:

```json
{
  "id": "2026-05-03_14-30-00_deepseek-v4-flash",
  "model": "deepseek/deepseek-v4-flash",
  "persona": "general",
  "created_at": "2026-05-03T14:30:00Z",
  "updated_at": "2026-05-03T14:45:00Z",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

Functions: `save(conversation)`, `load(id) -> conversation`, `list_all() -> list[summary]`, `delete(id)`.

Auto-saves after each assistant response.

### Persona Store (`core/personas.py`)

Plain text files in `~/.model-chat/personas/`. Ships with two defaults:

**general.txt:**
```
You are a helpful assistant. Be concise and direct.
```

**coder.txt:**
```
You are an expert programmer. Write clean, correct code. Explain concisely. Use markdown code blocks with language tags.
```

Users create custom personas by adding `.txt` files to the directory.

## CLI

### Technology

- `prompt_toolkit` for the interactive REPL (reliable on Windows, autocomplete, history)
- `rich` for markdown rendering and syntax highlighting in responses

### Interface

```
$ mchat
model-chat v1.0 — type /help for commands

[deepseek-v4-flash] > hello, explain python decorators briefly

Decorators are functions that wrap other functions to modify their behavior...

[deepseek-v4-flash] > /model gpt-4o
Switched to gpt-4o

[gpt-4o] > /effort high
Effort set to high

[gpt-4o] > /file src/app.py
Added src/app.py to context (142 lines)

[gpt-4o] > what does the main function do?
...
```

### Slash Commands

| Command | Description |
|---|---|
| `/model <name\|id>` | Switch model (alias or full OpenRouter ID) |
| `/models` | List available model aliases |
| `/effort low\|medium\|high` | Set reasoning effort |
| `/file <path>` | Add file contents to conversation context |
| `/persona <name>` | Load a system prompt |
| `/personas` | List available personas |
| `/save` | Save current conversation |
| `/load <id>` | Resume a saved conversation |
| `/list` | List saved conversations |
| `/clear` | Reset conversation (new chat) |
| `/multi` | Toggle multi-line input mode (Alt+Enter to submit) |
| `/help` | List all commands |
| `/quit` | Exit |

### Startup Flags

```
mchat                              # defaults
mchat --model gpt-4o               # start with specific model
mchat --persona coder              # start with specific persona
mchat --model gpt-4o --persona coder --effort high
```

### Entry Point

Installed via `pyproject.toml` as a console script:

```toml
[project.scripts]
mchat = "cli.app:main"
mchat-web = "web.backend.server:main"
```

## Web UI

### Backend (FastAPI)

Lives in `web/backend/server.py`. Imports `core` for all logic.

**Endpoints:**

```
GET  /api/models              → list of model aliases and IDs
GET  /api/personas            → list of available personas
GET  /api/conversations       → list of saved conversations (summaries)
GET  /api/conversations/:id   → load a specific conversation
POST /api/chat                → SSE stream of chat tokens
POST /api/conversations/save  → save current conversation
```

`POST /api/chat` request body:
```json
{
  "messages": [...],
  "model": "deepseek/deepseek-v4-flash",
  "persona": "coder",
  "effort": "medium"
}
```

Response: Server-Sent Events stream, each event is a token chunk.

Serves the built SvelteKit static files from a `static/` directory so no Node runtime is needed in production.

### Frontend (SvelteKit)

**Layout:**
- Left sidebar: conversation history list, "New Chat" button
- Top bar: model dropdown, effort toggle (3 buttons), persona selector
- Center: chat message panel with markdown rendering and syntax-highlighted code blocks
- Bottom: message input with send button, Enter to send, Shift+Enter for newline

**Styling:** Dark theme, clean and minimal. Tailwind CSS. Inspired by Claude's interface — muted backgrounds, clear typography, good contrast on code blocks.

**Streaming:** Uses EventSource to consume SSE from the backend. Tokens append to the current assistant message in real time.

**Build:** SvelteKit configured with `adapter-static` to produce a static bundle. The build output is copied into the Python package so FastAPI serves it. No Node needed at runtime.

## Data Directory

```
~/.model-chat/
├── config.yaml          # user overrides (default model, theme, etc.)
├── conversations/       # saved conversation JSON files
├── personas/            # system prompt .txt files
└── history              # prompt_toolkit command history
```

Created on first launch if it doesn't exist.

## Installation

### From source (primary method)

```bash
git clone https://github.com/<user>/model-chat.git
cd model-chat
pip install .
```

Requires: Python 3.10+, `OPENROUTER_API_KEY` set in environment.

The SvelteKit frontend is pre-built and included in the repo (or built during `pip install` via a build hook).

### Usage

```bash
mchat          # launch CLI
mchat --web    # launch web UI (opens browser)
```

### Docker (optional)

```dockerfile
FROM python:3.12-slim
COPY . /app
WORKDIR /app
RUN pip install .
EXPOSE 8000
CMD ["mchat", "--web", "--host", "0.0.0.0"]
```

```bash
docker build -t model-chat .
docker run -e OPENROUTER_API_KEY=sk-or-... -p 8000:8000 model-chat
```

## GitHub Repository

- Repo name: `model-chat`
- Public or private (user's choice)
- Includes: README with install instructions, MIT license
- `.gitignore` for Python, Node, and IDE files
- Pre-built frontend committed so users don't need Node to install

## Dependencies

### Python (pyproject.toml)

- `openai` — OpenRouter API client
- `prompt_toolkit` — CLI REPL
- `rich` — markdown/syntax rendering in CLI
- `fastapi` — web backend
- `uvicorn` — ASGI server
- `sse-starlette` — Server-Sent Events for FastAPI
- `pyyaml` — model registry config

### Node (frontend build only)

- `svelte` / `@sveltejs/kit`
- `tailwindcss`
- `marked` or `markdown-it` — markdown rendering
- `highlight.js` — code syntax highlighting
