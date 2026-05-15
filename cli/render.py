from rich.console import Console
from rich.markdown import Markdown

_console = Console()


def print_markdown(text: str) -> None:
    _console.print(Markdown(text))


def print_streaming_token(token: str) -> None:
    print(token, end="", flush=True)


def print_streaming_end() -> None:
    print()


def print_info(text: str) -> None:
    print(text)


def print_error(text: str) -> None:
    print(f"Error: {text}")


def print_success(text: str) -> None:
    print(text)


def print_usage(text: str) -> None:
    print(f"\033[90m{text}\033[0m")


def print_tool_call(name: str, arguments: dict) -> None:
    args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    _console.print(f"[dim]── {name}: {args_str} ──[/dim]")


def print_tool_result(name: str, output: str, is_error: bool) -> None:
    if is_error:
        for line in output.splitlines():
            _console.print(f"  [red]{line}[/red]")
        return

    lines = output.splitlines()

    # shell output is never truncated
    if name == "shell":
        for line in lines:
            _console.print(f"  [dim]{line}[/dim]")
        return

    # Other tools: truncate if > 20 lines (show first 5 + last 5)
    if len(lines) > 20:
        for line in lines[:5]:
            _console.print(f"  [dim]{line}[/dim]")
        _console.print(f"  [dim]... ({len(lines)} lines total)[/dim]")
        for line in lines[-5:]:
            _console.print(f"  [dim]{line}[/dim]")
    else:
        for line in lines:
            _console.print(f"  [dim]{line}[/dim]")
