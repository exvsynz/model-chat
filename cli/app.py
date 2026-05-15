import argparse
import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory

from core.client import ChatError
from core.agent import AgentLoop, TextDelta, ToolCallStart, ToolResult, Finished
from core.tools import create_default_registry
from core.models import ModelRegistry
from core.personas import PersonaStore
from core.store import ConversationStore
from core.memory import MemoryStore
from core.usage import UsageStats, format_usage
from cli.commands import parse_command, CommandHandler
from cli.completers import ChatCompleter
from cli.render import (
    print_markdown,
    print_streaming_token,
    print_streaming_end,
    print_info,
    print_error,
    print_usage,
    print_tool_call,
    print_tool_result,
)


DATA_DIR = Path.home() / ".model-chat"
BASE_PROMPT_PATH = Path(__file__).resolve().parents[1] / "config" / "base_prompt.txt"
_base_prompt_cache: str | None = None


def _load_base_prompt() -> str:
    global _base_prompt_cache
    if _base_prompt_cache is None:
        _base_prompt_cache = BASE_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return _base_prompt_cache

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


async def _spinner_task(start_time: float) -> None:
    idx = 0
    try:
        while True:
            elapsed = time.monotonic() - start_time
            frame = SPINNER_FRAMES[idx % len(SPINNER_FRAMES)]
            print(f"\r{frame} Thinking... {elapsed:.1f}s", end="", flush=True)
            idx += 1
            await asyncio.sleep(0.08)
    except asyncio.CancelledError:
        return


def get_prompt_session(handler: CommandHandler) -> PromptSession:
    completer = ChatCompleter(handler)
    history_path = DATA_DIR / "history"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    return PromptSession(
        completer=completer,
        history=FileHistory(str(history_path)),
    )


async def run_chat(handler: CommandHandler, user_input: str) -> None:
    handler.messages.append({"role": "user", "content": user_input})

    work_dir = Path.cwd()
    registry = create_default_registry(work_dir=work_dir)

    base = _load_base_prompt()
    persona = handler.system_prompt
    memory_section = handler.memory.format_for_prompt() if handler.memory else None
    parts = [base]
    if persona:
        parts.append(persona)
    if memory_section:
        parts.append(memory_section)
    effective_prompt = "\n\n".join(parts)

    async def ask_permission(name: str, arguments: dict) -> bool:
        if name in handler.allowed_tools:
            return True
        print_tool_call(name, arguments)
        try:
            answer = input("  Allow? (y/n/a): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        if answer == "a":
            handler.allowed_tools.add(name)
            return True
        return answer == "y"

    msg_snapshot = len(handler.messages)
    abort_event = asyncio.Event()

    loop = AgentLoop(
        model=handler.current_model,
        messages=handler.messages,
        system_prompt=effective_prompt,
        tools=registry,
        permission_fn=ask_permission,
        effort=handler.effort,
        abort_event=abort_event,
    )

    spinner = asyncio.create_task(_spinner_task(time.monotonic()))
    first_token = True
    full_response = ""

    original_handler = None
    import signal
    def _abort_handler(sig, frame):
        abort_event.set()
    if hasattr(signal, "SIGINT"):
        original_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, _abort_handler)

    try:
        async for event in loop.run():
            if isinstance(event, TextDelta):
                if first_token:
                    spinner.cancel()
                    print("\r\033[K", end="", flush=True)
                    first_token = False
                print_streaming_token(event.content)
                full_response += event.content
            elif isinstance(event, ToolCallStart):
                if first_token:
                    spinner.cancel()
                    print("\r\033[K", end="", flush=True)
                    first_token = False
                if not registry.needs_permission(event.name):
                    print_tool_call(event.name, event.arguments)
            elif isinstance(event, ToolResult):
                print_tool_result(event.name, event.output, event.is_error)
                spinner.cancel()
                spinner = asyncio.create_task(_spinner_task(time.monotonic()))
                first_token = True
            elif isinstance(event, Finished):
                if first_token:
                    spinner.cancel()
                    print("\r\033[K", end="", flush=True)
                print_streaming_end()
                if event.usage and event.usage.total_tokens > 0:
                    print_usage(format_usage(event.usage, model=handler.current_model))
                print()
    except ChatError as e:
        spinner.cancel()
        print("\r\033[K", end="", flush=True)
        print_error(str(e))
        del handler.messages[msg_snapshot:]
        return
    except Exception as e:
        spinner.cancel()
        print("\r\033[K", end="", flush=True)
        print_error(f"API error: {e}")
        del handler.messages[msg_snapshot:]
        return
    finally:
        if original_handler is not None:
            signal.signal(signal.SIGINT, original_handler)

    handler.last_response = full_response


async def repl(handler: CommandHandler) -> None:
    session = get_prompt_session(handler)

    model_short = handler.current_model.split("/")[-1] if "/" in handler.current_model else handler.current_model
    print_info(f"model-chat v1.0 — type /help for commands\n")

    while True:
        model_short = handler.current_model.split("/")[-1] if "/" in handler.current_model else handler.current_model
        try:
            if handler.multi_line:
                user_input = await session.prompt_async(
                    HTML(f"<aaa fg='ansicyan'>[{model_short}]</aaa> &gt; "),
                    multiline=True,
                )
            else:
                user_input = await session.prompt_async(HTML(f"<aaa fg='ansicyan'>[{model_short}]</aaa> &gt; "))
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
            if result == "retry":
                last_user_msg = handler.messages[-1]["content"]
                handler.messages.pop()
                await run_chat(handler, last_user_msg)
            if result == "edit":
                edit_input = await session.prompt_async(
                    HTML(f"<aaa fg='ansiyellow'>[{model_short}] edit</aaa> &gt; "),
                    default=handler.edit_text or "",
                )
                edit_input = edit_input.strip()
                if edit_input:
                    await run_chat(handler, edit_input)
                handler.edit_text = None
            continue

        await run_chat(handler, user_input)


def main():
    parser = argparse.ArgumentParser(description="Chat with any LLM via OpenRouter")
    parser.add_argument("--model", default=None, help="Starting model (alias or full ID)")
    parser.add_argument("--persona", default="coder", help="Starting persona (default: coder)")
    parser.add_argument("--effort", choices=["low", "medium", "high"], default=None, help="Reasoning effort")
    parser.add_argument("--web", action="store_true", help="Launch web UI instead of CLI")
    parser.add_argument("--host", default="127.0.0.1", help="Web server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")
    parser.add_argument("--no-auto-memory", action="store_true", help="Disable auto memory extraction")
    args = parser.parse_args()

    if args.web:
        import webbrowser
        import uvicorn
        from web.backend.server import create_app
        webbrowser.open(f"http://{args.host}:{args.port}")
        uvicorn.run(create_app(), host=args.host, port=args.port)
        return

    models = ModelRegistry.from_bundled()
    personas = PersonaStore.from_bundled()
    store = ConversationStore(DATA_DIR / "conversations")
    memory = MemoryStore(DATA_DIR / "memory")

    handler = CommandHandler(models=models, personas=personas, store=store, memory=memory)

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
    if args.no_auto_memory:
        handler.auto_memory = False
    else:
        handler.auto_memory = models.memory_config["auto_memory"]
    handler.max_memories = models.memory_config["max_memories"]

    asyncio.run(repl(handler))


if __name__ == "__main__":
    main()
