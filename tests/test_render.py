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
