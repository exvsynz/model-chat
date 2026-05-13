from unittest.mock import patch
from cli.render import print_markdown, print_streaming_token, print_streaming_end, print_info, print_error, print_success


def test_print_info(capsys):
    print_info("hello")
    assert capsys.readouterr().out == "hello\n"


def test_print_error(capsys):
    print_error("bad thing")
    assert capsys.readouterr().out == "Error: bad thing\n"


def test_print_success(capsys):
    print_success("done")
    assert capsys.readouterr().out == "done\n"


def test_print_streaming_token(capsys):
    print_streaming_token("tok")
    captured = capsys.readouterr()
    assert captured.out == "tok"


def test_print_streaming_end(capsys):
    print_streaming_end()
    captured = capsys.readouterr()
    assert captured.out == "\n"


def test_print_markdown():
    with patch("cli.render._console") as mock_console:
        print_markdown("# Hello")
        mock_console.print.assert_called_once()


def test_print_tool_call(capsys):
    """print_tool_call displays tool name and args."""
    from cli.render import print_tool_call
    print_tool_call("read_file", {"path": "src/main.py"})
    captured = capsys.readouterr()
    assert "read_file" in captured.out
    assert "src/main.py" in captured.out


def test_print_tool_result_short(capsys):
    """print_tool_result shows short results fully."""
    from cli.render import print_tool_result
    print_tool_result("read_file", "1\thello\n2\tworld", is_error=False)
    captured = capsys.readouterr()
    assert "hello" in captured.out
    assert "world" in captured.out


def test_print_tool_result_truncated(capsys):
    """print_tool_result truncates long results."""
    from cli.render import print_tool_result
    long_output = "\n".join(f"{i}\tline {i}" for i in range(1, 51))
    print_tool_result("read_file", long_output, is_error=False)
    captured = capsys.readouterr()
    assert "line 1" in captured.out
    assert "lines total" in captured.out


def test_print_tool_result_shell_not_truncated(capsys):
    """print_tool_result does not truncate shell output."""
    from cli.render import print_tool_result
    long_output = "\n".join(f"output line {i}" for i in range(1, 51))
    print_tool_result("shell", long_output, is_error=False)
    captured = capsys.readouterr()
    assert "output line 50" in captured.out


def test_print_tool_result_error(capsys):
    """print_tool_result shows errors in red."""
    from cli.render import print_tool_result
    print_tool_result("shell", "Error: command not found", is_error=True)
    captured = capsys.readouterr()
    assert "Error" in captured.out
