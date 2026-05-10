import json
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from core.agent import AgentLoop, TextDelta, ToolCallStart, ToolResult, Finished
from core.memory import MemoryStore, extract_memories
from core.models import ModelRegistry, fetch_all_models
from core.personas import PersonaStore
from core.store import ConversationStore
from core.tools import create_default_registry


logger = logging.getLogger("model-chat")

DATA_DIR = Path.home() / ".model-chat"


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
        system_prompt = None
        if req.persona:
            system_prompt = personas.load(req.persona)

        memory_section = memory.format_for_prompt()
        if memory_section:
            system_prompt = (system_prompt or "") + "\n\n" + memory_section

        async def permission_fn(name: str, arguments: dict) -> bool:
            return not registry.needs_permission(name)

        messages = list(req.messages)

        async def event_generator():
            loop = AgentLoop(
                model=req.model,
                messages=messages,
                system_prompt=system_prompt,
                tools=registry,
                permission_fn=permission_fn,
                effort=req.effort,
            )
            async for event in loop.run():
                if isinstance(event, TextDelta):
                    yield {"data": json.dumps({"type": "text", "content": event.content})}
                elif isinstance(event, ToolCallStart):
                    yield {"data": json.dumps({
                        "type": "tool_call",
                        "id": event.id,
                        "name": event.name,
                        "arguments": event.arguments,
                    })}
                elif isinstance(event, ToolResult):
                    yield {"data": json.dumps({
                        "type": "tool_result",
                        "id": event.id,
                        "name": event.name,
                        "output": event.output[:2000],
                        "is_error": event.is_error,
                    })}
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

        return EventSourceResponse(event_generator())

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
        logger.warning(f"Frontend static build not found at {static_dir} — web UI will not be served")

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
