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
