import asyncio
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from core.agent import AgentLoop, Finished, TextDelta, ToolCallStart, ToolResult
from core.memory import MemoryStore, extract_memories
from core.models import ModelRegistry, fetch_all_models
from core.personas import PersonaStore
from core.store import ConversationStore
from core.tools import create_default_registry

logger = logging.getLogger("model-chat")

DATA_DIR = Path.home() / ".model-chat"
BASE_PROMPT_PATH = Path(__file__).resolve().parents[2] / "config" / "base_prompt.txt"
_base_prompt_cache: str | None = None


def _load_base_prompt() -> str:
    global _base_prompt_cache
    if _base_prompt_cache is None:
        _base_prompt_cache = BASE_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return _base_prompt_cache


class ChatRequest(BaseModel):
    messages: list[dict]
    model: str
    persona: str | None = None
    effort: str | None = None


class SaveRequest(BaseModel):
    id: str
    model: str
    persona: str | None = None
    title: str | None = None
    created_at: str
    updated_at: str
    messages: list[dict]


class MemoryRequest(BaseModel):
    content: str
    type: str = "fact"


class PermissionResponse(BaseModel):
    approved: bool


def create_app() -> FastAPI:
    app = FastAPI(title="model-chat")

    if not os.environ.get("OPENROUTER_API_KEY"):
        logger.warning("OPENROUTER_API_KEY is not set — /api/chat will fail")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    models = ModelRegistry.from_bundled()
    personas = PersonaStore.from_bundled()
    store = ConversationStore(DATA_DIR / "conversations")
    memory = MemoryStore(DATA_DIR / "memory")
    registry = create_default_registry(work_dir=Path.cwd())
    pending_permissions: dict[str, asyncio.Future] = {}
    active_abort_events: dict[str, asyncio.Event] = {}

    @app.get("/api/models")
    def get_models():
        return {
            "aliases": dict(models.list_aliases()),
            "default": models.default,
        }

    @app.get("/api/models/all")
    def get_all_models():
        try:
            return fetch_all_models()
        except Exception:
            return []

    @app.get("/api/personas")
    def get_personas():
        return personas.list_names()

    @app.get("/api/conversations")
    def get_conversations():
        return store.list_all()

    @app.get("/api/conversations/{convo_id}")
    def get_conversation(convo_id: str):
        convo = store.load(convo_id)
        if convo is None:
            raise HTTPException(status_code=404, detail="not found")
        return convo

    @app.delete("/api/conversations/{convo_id}")
    def delete_conversation(convo_id: str):
        convo = store.load(convo_id)
        if convo is None:
            raise HTTPException(status_code=404, detail="not found")
        store.delete(convo_id)
        return {"status": "deleted", "id": convo_id}

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        base = _load_base_prompt()
        persona = personas.load(req.persona) if req.persona else None
        memory_section = memory.format_for_prompt()
        parts = [base]
        if persona:
            parts.append(persona)
        if memory_section:
            parts.append(memory_section)
        system_prompt = "\n\n".join(parts)

        messages = list(req.messages)
        event_queue: asyncio.Queue = asyncio.Queue()

        async def permission_fn(name: str, arguments: dict) -> bool:
            if not registry.needs_permission(name):
                return True
            request_id = str(uuid4())
            future = asyncio.get_event_loop().create_future()
            pending_permissions[request_id] = future
            await event_queue.put(
                {
                    "type": "permission_request",
                    "request_id": request_id,
                    "tool_name": name,
                    "arguments": arguments,
                }
            )
            try:
                return await asyncio.wait_for(future, timeout=120)
            except asyncio.TimeoutError:
                pending_permissions.pop(request_id, None)
                return False

        request_id = str(uuid4())
        abort_event = asyncio.Event()
        active_abort_events[request_id] = abort_event

        async def run_agent():
            try:
                loop = AgentLoop(
                    model=req.model,
                    messages=messages,
                    system_prompt=system_prompt,
                    tools=registry,
                    permission_fn=permission_fn,
                    effort=req.effort,
                    abort_event=abort_event,
                )
                async for event in loop.run():
                    await event_queue.put(event)
            except Exception as e:
                logger.exception("Agent loop error")
                await event_queue.put({"type": "error", "message": str(e)})
            finally:
                active_abort_events.pop(request_id, None)
                await event_queue.put(None)

        async def event_generator():
            task = asyncio.create_task(run_agent())
            yield {"data": json.dumps({"type": "session", "request_id": request_id})}
            try:
                while True:
                    event = await event_queue.get()
                    if event is None:
                        break
                    if isinstance(event, dict):
                        yield {"data": json.dumps(event)}
                    elif isinstance(event, TextDelta):
                        yield {"data": json.dumps({"type": "text", "content": event.content})}
                    elif isinstance(event, ToolCallStart):
                        yield {
                            "data": json.dumps(
                                {
                                    "type": "tool_call",
                                    "id": event.id,
                                    "name": event.name,
                                    "arguments": event.arguments,
                                }
                            )
                        }
                    elif isinstance(event, ToolResult):
                        yield {
                            "data": json.dumps(
                                {
                                    "type": "tool_result",
                                    "id": event.id,
                                    "name": event.name,
                                    "output": event.output[:2000],
                                    "is_error": event.is_error,
                                }
                            )
                        }
                    elif isinstance(event, Finished):
                        usage = None
                        if event.usage and event.usage.total_tokens > 0:
                            usage = {
                                "prompt_tokens": event.usage.prompt_tokens,
                                "completion_tokens": event.usage.completion_tokens,
                                "total_tokens": event.usage.total_tokens,
                                "elapsed_seconds": event.usage.elapsed_seconds,
                            }
                        yield {"data": json.dumps({"type": "done", "usage": usage})}
            finally:
                if not task.done():
                    task.cancel()

        return EventSourceResponse(event_generator())

    @app.post("/api/chat/permission/{request_id}")
    async def handle_permission(request_id: str, body: PermissionResponse):
        future = pending_permissions.pop(request_id, None)
        if not future or future.done():
            raise HTTPException(status_code=404, detail="No pending permission request")
        future.set_result(body.approved)
        return {"status": "ok"}

    @app.post("/api/chat/abort/{request_id}")
    async def abort_chat(request_id: str):
        event = active_abort_events.get(request_id)
        if not event:
            raise HTTPException(status_code=404, detail="No active session with that ID")
        event.set()
        return {"status": "aborted"}

    @app.post("/api/conversations/save")
    async def save_conversation(req: SaveRequest):
        store.save(req.model_dump())
        extracted = []
        if len(req.messages) >= 4:
            try:
                raw_memories = await extract_memories(req.messages, req.model)
                for mem in raw_memories:
                    if not memory._is_duplicate(mem["content"]):
                        memory.add(mem["content"], mem.get("type", "fact"))
                        extracted.append(mem["content"])
            except Exception:
                pass
        return {"status": "saved", "id": req.id, "extracted_memories": extracted}

    @app.get("/api/memories")
    def get_memories():
        return memory.list_all()

    @app.post("/api/memories")
    def add_memory(req: MemoryRequest):
        if memory._is_duplicate(req.content):
            return {"status": "duplicate", "file": None}
        filename = memory.add(req.content, req.type)
        return {"status": "saved", "file": filename}

    @app.delete("/api/memories/{slug}")
    def delete_memory(slug: str):
        if not memory.remove(slug):
            raise HTTPException(status_code=404, detail="not found")
        return {"status": "deleted", "slug": slug}

    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    else:
        logger.warning(
            f"Frontend static build not found at {static_dir} — web UI will not be served"
        )

    return app


def main():
    import argparse
    import webbrowser

    parser = argparse.ArgumentParser(description="model-chat web server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    webbrowser.open(f"http://{args.host}:{args.port}")
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
