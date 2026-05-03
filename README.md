# model-chat

Chat with any LLM via OpenRouter. CLI and web UI.

## Install

```bash
git clone https://github.com/exvsynz/model-chat.git
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
