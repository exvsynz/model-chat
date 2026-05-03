# model-chat

Chat with any LLM via [OpenRouter](https://openrouter.ai). CLI REPL and web UI.

## Features

- **Multi-model**: Switch between any OpenRouter model mid-conversation
- **CLI REPL**: prompt_toolkit-based terminal chat with slash commands
- **Web UI**: SvelteKit frontend served by FastAPI, with searchable model dropdown
- **Personas**: System prompt templates (coder, tutor, translator, reviewer, writer, shell, general)
- **Conversation persistence**: Save/load/list/delete conversations as JSON
- **Reasoning effort**: Toggle DeepSeek/Qwen thinking depth (low/medium/high)
- **Streaming**: Token-by-token output in both CLI and web (SSE)
- **Model browsing**: Search all 300+ OpenRouter models from CLI or web
- **File context**: Attach file contents to your conversation via `/file`
- **Token usage**: Displays token count and response time after each message
- **Smart completion**: Tab-complete commands, model names, personas, file paths
- **Theme toggle**: Switch between dark and light mode in the web UI
- **Auto-titles**: Conversations get titles from the first message
- **Memory**: Persistent memory across conversations with auto-extraction

## Install

```bash
git clone https://github.com/exvsynz/model-chat.git
cd model-chat
pip install .
```

For development:

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+ and an OpenRouter API key:

```bash
# Linux/macOS
export OPENROUTER_API_KEY=sk-or-...

# Windows
setx OPENROUTER_API_KEY "sk-or-..."
```

## Usage

### CLI

```bash
mchat                                    # start chatting (default: deepseek-v4-flash)
mchat --model qwen3-coder --persona coder  # with options
mchat --effort high                      # enable deep reasoning
```

### Web UI

```bash
mchat --web                              # http://127.0.0.1:8000
mchat --web --host 0.0.0.0 --port 3000   # custom bind
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `/model <name\|id>` | Switch model (alias or full OpenRouter ID) |
| `/models` | List configured model aliases |
| `/browse [search]` | Search all OpenRouter models |
| `/effort low\|medium\|high` | Set reasoning effort |
| `/persona <name>` | Load a system prompt |
| `/personas` | List available personas |
| `/file <path>` | Add file contents to context |
| `/save` | Save current conversation |
| `/load <id>` | Resume a saved conversation |
| `/list` | List saved conversations |
| `/clear` | Reset conversation |
| `/info` | Show current session state |
| `/retry` | Regenerate last response |
| `/edit` | Edit and re-send last message |
| `/copy` | Copy last response to clipboard |
| `/export <path>` | Export conversation as markdown |
| `/remember <text>` | Save a memory for future conversations |
| `/forget <slug\|keyword>` | Remove a saved memory |
| `/memories` | List all saved memories |
| `/automemory` | Toggle auto memory extraction |
| `/multi` | Toggle multi-line input |
| `/help` | Show help |
| `/quit` | Exit |

### Model Aliases

Short names for common models — see [`config/models.yaml`](config/models.yaml) for the full list. You can also use any full OpenRouter model ID directly (e.g. `openai/gpt-4o`).

### Personas

System prompt templates in [`config/personas/`](config/personas/):

| Name | Purpose |
|------|---------|
| general | Balanced assistant (default) |
| coder | Code-focused, concise output |
| reviewer | Code review with actionable feedback |
| writer | Technical writing, docs, emails |
| tutor | Patient step-by-step teaching |
| translator | English/Chinese translation |
| shell | Shell command generation |

## Architecture

```
model-chat/
  core/           # Shared library
    client.py     # AsyncOpenAI streaming client (OpenRouter)
    models.py     # Model registry + alias resolution + fetch_all_models()
    personas.py   # System prompt loader
    store.py      # JSON conversation persistence
    memory.py     # MemoryStore + auto-extraction
    usage.py      # Token usage stats and formatting
  cli/            # Terminal interface
    app.py        # Entry point, prompt_toolkit REPL
    commands.py   # Slash command handler (19 commands)
    completers.py # Smart tab completion
    render.py     # Output formatting (Rich markdown + plain text)
  web/
    backend/
      server.py   # FastAPI + SSE streaming + static file serving
    frontend/     # SvelteKit 5 + Tailwind CSS v4
  config/
    models.yaml   # Model aliases
    personas/     # System prompt .txt files
  tests/          # pytest + pytest-asyncio
```

## Docker

```bash
docker build -t model-chat .
docker run -e OPENROUTER_API_KEY=sk-or-... -p 8000:8000 model-chat
```

## Testing

```bash
pytest tests/ -v
```

## License

MIT
