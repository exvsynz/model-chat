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

from core.client import chat_stream
from core.models import ModelRegistry, fetch_all_models
from core.personas import PersonaStore
from core.store import ConversationStore


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
    created_at: str
    updated_at: str
    messages: list[dict]


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

        async def event_generator():
            async for token in chat_stream(
                messages=req.messages,
                model=req.model,
                system_prompt=system_prompt,
                effort=req.effort,
            ):
                yield {"data": json.dumps({"token": token})}
            yield {"data": json.dumps({"done": True})}

        return EventSourceResponse(event_generator())

    @app.post("/api/conversations/save")
    def save_conversation(req: SaveRequest):
        store.save(req.model_dump())
        return {"status": "saved", "id": req.id}

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
