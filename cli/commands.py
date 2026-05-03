import asyncio
import subprocess
import sys
from pathlib import Path
from core.models import ModelRegistry
from core.personas import PersonaStore
from core.store import ConversationStore
from core.memory import MemoryStore, extract_memories
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
    "browse": ("/browse [search]", "Search all OpenRouter models"),
    "effort": ("/effort low|medium|high", "Set reasoning effort"),
    "file": ("/file <path>", "Add file contents to context"),
    "persona": ("/persona <name>", "Load a system prompt"),
    "personas": ("/personas", "List available personas"),
    "save": ("/save", "Save current conversation"),
    "load": ("/load <id>", "Resume a saved conversation"),
    "list": ("/list", "List saved conversations"),
    "clear": ("/clear", "Reset conversation"),
    "multi": ("/multi", "Toggle multi-line input"),
    "info": ("/info", "Show current session state"),
    "retry": ("/retry", "Regenerate last response"),
    "edit": ("/edit", "Edit and re-send last message"),
    "copy": ("/copy", "Copy last response to clipboard"),
    "export": ("/export <path>", "Export conversation as markdown"),
    "remember": ("/remember <text>", "Save a memory"),
    "forget": ("/forget <slug|keyword>", "Forget a memory"),
    "memories": ("/memories", "List saved memories"),
    "automemory": ("/automemory", "Toggle auto-extraction"),
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
        memory: MemoryStore | None = None,
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
        self.edit_text: str | None = None
        self.last_response: str | None = None
        self.memory = memory
        self.auto_memory: bool = True
        self.max_memories: int = 100

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

    def _cmd_browse(self, args: str) -> str | None:
        from core.models import fetch_all_models
        try:
            all_models = fetch_all_models()
        except Exception as e:
            print_error(f"Failed to fetch models: {e}")
            return None
        if args:
            query = args.lower()
            all_models = [m for m in all_models if query in m["id"].lower() or query in m["name"].lower()]
        if not all_models:
            print_info("No models found")
            return None
        lines = [f"  {m['id']:<55} {m['name']}" for m in all_models[:50]]
        suffix = f"\n  ... and {len(all_models) - 50} more (narrow your search)" if len(all_models) > 50 else ""
        print_info(f"Models ({len(all_models)} results):\n" + "\n".join(lines) + suffix)
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

        # Auto-extraction (skip if at memory cap)
        if (self.auto_memory and self.memory and len(self.messages) >= 4
                and len(self.memory.list_all()) < self.max_memories):
            extraction_model = self.current_model
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        memories = pool.submit(
                            asyncio.run,
                            extract_memories(self.messages, extraction_model)
                        ).result()
                else:
                    memories = loop.run_until_complete(
                        extract_memories(self.messages, extraction_model)
                    )
            except Exception:
                memories = []

            saved_count = 0
            for mem in memories:
                if not self.memory._is_duplicate(mem["content"]):
                    self.memory.add(mem["content"], mem.get("type", "fact"))
                    saved_count += 1
            if saved_count > 0:
                print_info(f"Auto-saved {saved_count} {'memory' if saved_count == 1 else 'memories'}")

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

    def _cmd_info(self, args: str) -> str | None:
        model = self.current_model
        model_short = model.split("/")[-1] if "/" in model else model
        persona = self.persona_name or "(none)"
        effort = self.effort or "(default)"
        msg_count = len(self.messages)
        print_info(f"  Model:    {model_short} ({model})")
        print_info(f"  Persona:  {persona}")
        print_info(f"  Effort:   {effort}")
        print_info(f"  Messages: {msg_count}")
        return None

    def _cmd_retry(self, args: str) -> str | None:
        if not self.messages:
            print_error("No messages to retry")
            return None
        if self.messages[-1]["role"] == "assistant":
            self.messages.pop()
        if not self.messages or self.messages[-1]["role"] != "user":
            print_error("No user message to retry")
            return None
        return "retry"

    def _cmd_edit(self, args: str) -> str | None:
        if not self.messages:
            print_error("No messages to edit")
            return None
        if self.messages[-1]["role"] == "assistant":
            self.messages.pop()
        if self.messages and self.messages[-1]["role"] == "user":
            self.edit_text = self.messages.pop()["content"]
            return "edit"
        print_error("No user message to edit")
        return None

    def _cmd_copy(self, args: str) -> str | None:
        if not self.last_response:
            print_error("No response to copy")
            return None
        try:
            if sys.platform == "win32":
                subprocess.run(["clip"], input=self.last_response.encode("utf-8"), check=True)
            elif sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=self.last_response.encode("utf-8"), check=True)
            else:
                subprocess.run(["xclip", "-selection", "clipboard"], input=self.last_response.encode("utf-8"), check=True)
            print_success("Copied to clipboard")
        except Exception as e:
            print_error(f"Failed to copy: {e}")
        return None

    def _cmd_export(self, args: str) -> str | None:
        if not self.messages:
            print_error("No messages to export")
            return None
        if not args:
            print_error("Usage: /export <path>")
            return None
        path = Path(args).expanduser()
        lines = [f"# Conversation — {self.current_model}\n"]
        for msg in self.messages:
            role = msg["role"].capitalize()
            lines.append(f"## {role}\n")
            lines.append(msg["content"])
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        print_success(f"Exported {len(self.messages)} messages to {path}")
        return None

    def _cmd_remember(self, args: str) -> str | None:
        if not args:
            print_error("Usage: /remember <text>")
            return None
        if self.memory is None:
            print_error("Memory not available")
            return None
        if len(self.memory.list_all()) >= self.max_memories:
            print_error(f"Memory limit reached ({self.max_memories}). Use /forget to remove old memories.")
            return None
        if self.memory._is_duplicate(args):
            entries = self.memory.list_all()
            for entry in entries:
                words = self.memory._significant_words(args)
                existing = self.memory._significant_words(entry["summary"])
                if len(words & existing) >= 3:
                    print_info(f"Similar memory already exists: {entry['summary']}")
                    return None
        filename = self.memory.add(args, "fact")
        print_success(f"Remembered: {args[:80]}")
        return None

    def _cmd_forget(self, args: str) -> str | None:
        if not args:
            print_error("Usage: /forget <slug or keyword>")
            return None
        if self.memory is None:
            print_error("Memory not available")
            return None
        if self.memory.remove(args):
            print_success(f"Forgot: {args}")
            return None
        # Try common category prefixes when bare slug provided
        for prefix in ("fact_", "pref_", "project_", "note_"):
            if self.memory.remove(f"{prefix}{args}"):
                print_success(f"Forgot: {args}")
                return None
        entries = self.memory.list_all()
        matches = [e for e in entries if args.lower() in e["summary"].lower()]
        if not matches:
            print_error(f"No memory found matching: {args}")
        elif len(matches) == 1:
            slug = matches[0]["file"].removesuffix(".md")
            self.memory.remove(slug)
            print_success(f"Forgot: {matches[0]['summary']}")
        else:
            lines = [f"  {e['file'].removesuffix('.md')}: {e['summary']}" for e in matches]
            print_info("Multiple matches — be more specific:\n" + "\n".join(lines))
        return None

    def _cmd_memories(self, args: str) -> str | None:
        if self.memory is None:
            print_error("Memory not available")
            return None
        entries = self.memory.list_all()
        if not entries:
            print_info("No memories saved")
            return None
        lines = [f"  {e['file'].removesuffix('.md')}: {e['summary']}" for e in entries]
        print_info(f"Memories ({len(entries)}):\n" + "\n".join(lines))
        return None

    def _cmd_automemory(self, args: str) -> str | None:
        self.auto_memory = not self.auto_memory
        state = "on" if self.auto_memory else "off"
        print_success(f"Auto-memory: {state}")
        return None

    def _cmd_help(self, args: str) -> str | None:
        print_info(self.registry.get_help())
        return None

    def _cmd_quit(self, args: str) -> str | None:
        return "quit"
