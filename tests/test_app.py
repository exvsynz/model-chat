import sys
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

        with patch.object(sys, "argv", ["mchat"]):
            from cli.app import main
            main()

        mock_asyncio.run.assert_called_once()


def test_main_web_launches_uvicorn():
    """main() with --web starts uvicorn instead of REPL."""
    mock_uvicorn = MagicMock()
    mock_webbrowser = MagicMock()
    mock_create_app = MagicMock(return_value=MagicMock())

    with patch.dict(sys.modules, {
        "uvicorn": mock_uvicorn,
        "webbrowser": mock_webbrowser,
        "web.backend.server": MagicMock(create_app=mock_create_app),
    }):
        with patch.object(sys, "argv", ["mchat", "--web"]):
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

    with patch.dict(sys.modules, {
        "uvicorn": mock_uvicorn,
        "webbrowser": mock_webbrowser,
        "web.backend.server": MagicMock(create_app=mock_create_app),
    }):
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
        try:
            await task
        except asyncio.CancelledError:
            pass

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
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert task.done() and not task.cancelled()
