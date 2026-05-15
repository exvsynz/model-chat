import contextlib
import sys
from unittest.mock import MagicMock, patch

import pytest


def test_main_parses_default_args():
    """main() with no args starts the REPL."""
    with (
        patch("cli.app.asyncio") as mock_asyncio,
        patch("cli.app.ModelRegistry") as mock_mr,
        patch("cli.app.PersonaStore") as mock_ps,
        patch("cli.app.ConversationStore"),
    ):
        mock_mr.from_bundled.return_value = MagicMock(default="test/model")
        mock_ps.from_bundled.return_value = MagicMock()

        with patch.object(sys, "argv", ["mchat"]):
            from cli.app import main

            main()

        mock_asyncio.run.assert_called_once()


def test_main_web_launches_uvicorn():
    """main() with --web starts uvicorn instead of REPL."""
    mock_uvicorn = MagicMock()
    mock_webbrowser = MagicMock()
    mock_create_app = MagicMock(return_value=MagicMock())

    with (
        patch.dict(
            sys.modules,
            {
                "uvicorn": mock_uvicorn,
                "webbrowser": mock_webbrowser,
                "web.backend.server": MagicMock(create_app=mock_create_app),
            },
        ),
        patch.object(sys, "argv", ["mchat", "--web"]),
    ):
        from cli.app import main

        main()

    mock_uvicorn.run.assert_called_once()
    call_kwargs = mock_uvicorn.run.call_args
    assert call_kwargs.kwargs["host"] == "127.0.0.1"
    assert call_kwargs.kwargs["port"] == 8000


def test_main_web_custom_host_port():
    """main() with --web --host --port passes them through."""
    mock_uvicorn = MagicMock()
    mock_webbrowser = MagicMock()
    mock_create_app = MagicMock(return_value=MagicMock())

    with (
        patch.dict(
            sys.modules,
            {
                "uvicorn": mock_uvicorn,
                "webbrowser": mock_webbrowser,
                "web.backend.server": MagicMock(create_app=mock_create_app),
            },
        ),
        patch.object(sys, "argv", ["mchat", "--web", "--host", "0.0.0.0", "--port", "3000"]),
    ):
        from cli.app import main

        main()

    call_kwargs = mock_uvicorn.run.call_args
    assert call_kwargs.kwargs["host"] == "0.0.0.0"
    assert call_kwargs.kwargs["port"] == 3000


def test_main_model_arg_resolves():
    """main() with --model resolves the alias via ModelRegistry."""
    with (
        patch("cli.app.asyncio"),
        patch("cli.app.ModelRegistry") as mock_mr,
        patch("cli.app.PersonaStore") as mock_ps,
        patch("cli.app.ConversationStore"),
        patch("cli.app.CommandHandler") as mock_ch,
    ):
        mock_registry = MagicMock(default="test/model")
        mock_registry.resolve.return_value = "deepseek/deepseek-r1"
        mock_mr.from_bundled.return_value = mock_registry
        mock_ps.from_bundled.return_value = MagicMock()
        mock_handler = MagicMock()
        mock_ch.return_value = mock_handler

        with patch.object(sys, "argv", ["mchat", "--model", "deepseek-r1"]):
            from cli.app import main

            main()

        mock_registry.resolve.assert_called_with("deepseek-r1")
        assert mock_handler.current_model == "deepseek/deepseek-r1"


@pytest.mark.asyncio
async def test_spinner_task_outputs_frames():
    """_spinner_task prints spinner frames with elapsed time."""
    import asyncio
    import time

    from cli.app import _spinner_task

    output = []
    with patch("builtins.print", side_effect=lambda *a, **kw: output.append(a[0] if a else "")):
        task = asyncio.create_task(_spinner_task(time.monotonic()))
        await asyncio.sleep(0.25)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    assert len(output) >= 2
    assert "Thinking..." in output[0]
    assert "s" in output[0]


@pytest.mark.asyncio
async def test_spinner_task_cancels_cleanly():
    """_spinner_task does not raise when cancelled."""
    import asyncio
    import time

    from cli.app import _spinner_task

    with patch("builtins.print"):
        task = asyncio.create_task(_spinner_task(time.monotonic()))
        await asyncio.sleep(0.1)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    assert task.done() and not task.cancelled()


@pytest.mark.asyncio
async def test_run_chat_shows_and_clears_spinner():
    """run_chat starts spinner, clears it on first token."""
    import asyncio

    from cli.app import run_chat
    from core.client import ContentDelta, StreamEnd
    from core.usage import UsageStats

    handler = MagicMock()
    handler.messages = []
    handler.current_model = "test/model"
    handler.system_prompt = None
    handler.effort = None
    handler.memory = None
    handler.last_response = None
    handler.allowed_tools = set()

    async def fake_stream(*a, **kw):
        await asyncio.sleep(0.15)
        yield ContentDelta(text="Hello")
        yield ContentDelta(text=" world")
        yield StreamEnd(
            usage=UsageStats(
                prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=1.0
            ),
            finish_reason="stop",
        )

    printed = []

    def capture_print(*args, **kwargs):
        if args:
            printed.append(str(args[0]))

    with (
        patch("core.agent.stream_completion", side_effect=fake_stream),
        patch("builtins.print", side_effect=capture_print),
        patch("cli.app.print_streaming_token", side_effect=lambda t: printed.append(f"TOKEN:{t}")),
        patch("cli.app.print_streaming_end"),
        patch("cli.app.print_usage"),
    ):
        await run_chat(handler, "hi")

    spinner_frames = [p for p in printed if "Thinking..." in p]
    assert len(spinner_frames) >= 1

    clear_frames = [p for p in printed if "\r\033[K" in p]
    assert len(clear_frames) >= 1

    token_frames = [p for p in printed if p.startswith("TOKEN:")]
    assert "TOKEN:Hello" in token_frames
    assert "TOKEN: world" in token_frames
