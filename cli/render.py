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
