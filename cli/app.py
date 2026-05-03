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
from core.usage import UsageStats, format_usage
from cli.commands import parse_command, CommandHandler
from cli.render import (
    print_markdown,
    print_streaming_token,
    print_streaming_end,
    print_info,
    print_error,
    print_usage,
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


async def repl(handler: CommandHandler) -> None:
    session = get_prompt_session(handler)

    model_short = handler.current_model.split("/")[-1] if "/" in handler.current_model else handler.current_model
    print_info(f"model-chat v1.0 — type /help for commands\n")

    while True:
        model_short = handler.current_model.split("/")[-1] if "/" in handler.current_model else handler.current_model
        try:
            if handler.multi_line:
                user_input = await session.prompt_async(
                    f"[{model_short}] > ",
                    multiline=True,
                )
            else:
                user_input = await session.prompt_async(f"[{model_short}] > ")
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
                    f"[{model_short}] edit> ",
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
    parser.add_argument("--persona", default=None, help="Starting persona")
    parser.add_argument("--effort", choices=["low", "medium", "high"], default=None, help="Reasoning effort")
    parser.add_argument("--web", action="store_true", help="Launch web UI instead of CLI")
    parser.add_argument("--host", default="127.0.0.1", help="Web server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")
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
