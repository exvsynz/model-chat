from pathlib import Path
from core.models import ModelRegistry
from core.personas import PersonaStore
from core.store import ConversationStore
from cli.render import print_info, print_error, print_success


def parse_command(text: str) -> tuple[str | None, str]:
    text = text.strip()
    if not text.startswith("/"):
        return None, text
    parts = text[1:].split(None, 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""
    return cmd, args


COMMAND_HELP = {
    "model": ("/model <name|id>", "Switch model"),
    "models": ("/models", "List available model aliases"),
    "effort": ("/effort low|medium|high", "Set reasoning effort"),
    "file": ("/file <path>", "Add file contents to context"),
    "persona": ("/persona <name>", "Load a system prompt"),
    "personas": ("/personas", "List available personas"),
    "save": ("/save", "Save current conversation"),
    "load": ("/load <id>", "Resume a saved conversation"),
    "list": ("/list", "List saved conversations"),
    "clear": ("/clear", "Reset conversation"),
    "multi": ("/multi", "Toggle multi-line input"),
    "help": ("/help", "Show this help"),
    "quit": ("/quit", "Exit"),
}


class CommandRegistry:
    def __init__(self):
        self._commands = COMMAND_HELP

    def list_commands(self) -> list[str]:
        return list(self._commands.keys())

    def get_help(self) -> str:
        lines = []
        for cmd, (usage, desc) in self._commands.items():
            lines.append(f"  {usage:<30} {desc}")
        return "\n".join(lines)


class CommandHandler:
    def __init__(
        self,
        models: ModelRegistry,
        personas: PersonaStore,
        store: ConversationStore,
    ):
        self.models = models
        self.personas = personas
        self.store = store
        self.current_model: str = models.default
        self.effort: str | None = None
        self.system_prompt: str | None = None
        self.persona_name: str | None = None
        self.messages: list[dict] = []
        self.multi_line: bool = False
        self.registry = CommandRegistry()

    def handle(self, cmd: str, args: str) -> str | None:
        handler = getattr(self, f"_cmd_{cmd}", None)
        if handler is None:
            print_error(f"Unknown command: /{cmd}")
            return None
        return handler(args)

    def _cmd_model(self, args: str) -> str | None:
        if not args:
            print_info(f"Current model: {self.current_model}")
            return None
        self.current_model = self.models.resolve(args)
        print_success(f"Switched to {self.current_model}")
        return None

    def _cmd_models(self, args: str) -> str | None:
        aliases = self.models.list_aliases()
        lines = [f"  {alias:<25} {full_id}" for alias, full_id in aliases]
        print_info("Available models:\n" + "\n".join(lines))
        return None

    def _cmd_effort(self, args: str) -> str | None:
        if args not in ("low", "medium", "high"):
            print_error("Usage: /effort low|medium|high")
            return None
        self.effort = args
        print_success(f"Effort set to {args}")
        return None

    def _cmd_file(self, args: str) -> str | None:
        if not args:
            print_error("Usage: /file <path>")
            return None
        path = Path(args).expanduser()
        if not path.exists():
            print_error(f"File not found: {path}")
            return None
        content = path.read_text(encoding="utf-8", errors="replace")
        line_count = len(content.splitlines())
        self.messages.append({
            "role": "user",
            "content": f"<file path=\"{path}\">\n{content}\n</file>",
        })
        print_success(f"Added {path.name} to context ({line_count} lines)")
        return None

    def _cmd_persona(self, args: str) -> str | None:
        if not args:
            if self.persona_name:
                print_info(f"Current persona: {self.persona_name}")
            else:
                print_info("No persona set")
            return None
        prompt = self.personas.load(args)
        if prompt is None:
            print_error(f"Persona not found: {args}")
            return None
        self.system_prompt = prompt
        self.persona_name = args
        print_success(f"Persona set to {args}")
        return None

    def _cmd_personas(self, args: str) -> str | None:
        names = self.personas.list_names()
        if not names:
            print_info("No personas found")
            return None
        print_info("Available personas: " + ", ".join(names))
        return None

    def _cmd_save(self, args: str) -> str | None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        model_short = self.current_model.split("/")[-1] if "/" in self.current_model else self.current_model
        convo_id = now.strftime(f"%Y-%m-%d_%H-%M-%S_{model_short}")
        convo = {
            "id": convo_id,
            "model": self.current_model,
            "persona": self.persona_name or "",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "messages": self.messages,
        }
        self.store.save(convo)
        print_success(f"Saved as {convo_id}")
        return None

    def _cmd_load(self, args: str) -> str | None:
        if not args:
            print_error("Usage: /load <id>")
            return None
        convo = self.store.load(args)
        if convo is None:
            print_error(f"Conversation not found: {args}")
            return None
        self.messages = convo.get("messages", [])
        self.current_model = convo.get("model", self.current_model)
        self.persona_name = convo.get("persona") or None
        if self.persona_name:
            self.system_prompt = self.personas.load(self.persona_name)
        print_success(f"Loaded {args} ({len(self.messages)} messages, model: {self.current_model})")
        return None

    def _cmd_list(self, args: str) -> str | None:
        summaries = self.store.list_all()
        if not summaries:
            print_info("No saved conversations")
            return None
        lines = []
        for s in summaries:
            lines.append(f"  {s['id']:<45} {s['model']:<30} {s['message_count']} msgs")
        print_info("Saved conversations:\n" + "\n".join(lines))
        return None

    def _cmd_clear(self, args: str) -> str | None:
        self.messages = []
        print_success("Conversation cleared")
        return None

    def _cmd_multi(self, args: str) -> str | None:
        self.multi_line = not self.multi_line
        state = "on" if self.multi_line else "off"
        print_success(f"Multi-line input {state} (Alt+Enter to submit)")
        return None

    def _cmd_help(self, args: str) -> str | None:
        print_info(self.registry.get_help())
        return None

    def _cmd_quit(self, args: str) -> str | None:
        return "quit"
