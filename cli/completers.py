from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class ChatCompleter(Completer):
    def __init__(self, handler):
        self._handler = handler

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor

        if not text.startswith("/"):
            return

        parts = text.split(None, 1)
        cmd_part = parts[0]

        if len(parts) == 1 and not text.endswith(" "):
            commands = ["/" + c for c in self._handler.registry.list_commands()]
            for cmd in commands:
                if cmd.startswith(cmd_part):
                    yield Completion(cmd, start_position=-len(cmd_part))
            return

        if len(parts) < 2:
            arg_text = ""
        else:
            arg_text = parts[1]

        cmd_name = cmd_part[1:]

        if cmd_name == "model":
            aliases = self._handler.models.list_aliases()
            for alias, _ in aliases:
                if alias.startswith(arg_text):
                    yield Completion(alias, start_position=-len(arg_text))

        elif cmd_name == "persona":
            names = self._handler.personas.list_names()
            for name in names:
                if name.startswith(arg_text):
                    yield Completion(name, start_position=-len(arg_text))

        elif cmd_name == "load":
            summaries = self._handler.store.list_all()
            for s in summaries:
                convo_id = s["id"]
                if convo_id.startswith(arg_text):
                    yield Completion(convo_id, start_position=-len(arg_text))

        elif cmd_name == "file":
            from pathlib import Path
            prefix = Path(arg_text) if arg_text else Path(".")
            parent = prefix.parent if arg_text and not arg_text.endswith("/") else prefix
            stem = prefix.name if arg_text and not arg_text.endswith("/") else ""
            try:
                for p in parent.iterdir():
                    name = str(p)
                    if name.startswith(arg_text) or p.name.startswith(stem):
                        yield Completion(str(p), start_position=-len(arg_text))
            except OSError:
                pass
