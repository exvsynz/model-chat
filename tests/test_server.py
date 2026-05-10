import json
import logging

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from web.backend.server import create_app
from core.agent import TextDelta, ToolCallStart, ToolResult, Finished
from core.usage import UsageStats


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_get_models(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "aliases" in data
    assert "default" in data


@pytest.mark.asyncio
async def test_get_personas(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/personas")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "general" in data


@pytest.mark.asyncio
async def test_get_conversations_empty(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/conversations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_chat_requires_messages(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/chat", json={"model": "openai/gpt-4o"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_conversation_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete("/api/conversations/nonexistent")
    assert resp.status_code == 404


def test_server_logs_warning_when_no_api_key(app, caplog):
    """Server should log a warning on startup if OPENROUTER_API_KEY is not set."""
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {}, clear=True):
        with caplog.at_level(logging.WARNING):
            from web.backend.server import create_app
            test_app = create_app()
    assert any("OPENROUTER_API_KEY" in r.message for r in caplog.records)


def test_server_logs_warning_when_no_static_build(app, caplog):
    """Server should log a warning if the frontend static build directory is missing."""
    from unittest.mock import patch
    from pathlib import Path
    with caplog.at_level(logging.WARNING):
        with patch.object(Path, 'exists', return_value=False):
            from web.backend.server import create_app
            test_app = create_app()
    assert any("static" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_get_memories_empty(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/memories")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_post_memory(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/memories", json={"content": "User is Josh", "type": "user"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    assert "file" in data


@pytest.mark.asyncio
async def test_get_memories_after_add(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/memories", json={"content": "User is Josh", "type": "user"})
        resp = await client.get("/api/memories")
    assert resp.status_code == 200
    memories = resp.json()
    assert len(memories) >= 1
    assert any("Josh" in m["summary"] for m in memories)


@pytest.mark.asyncio
async def test_delete_memory(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/memories", json={"content": "User is Josh", "type": "user"})
        slug = resp.json()["file"].removesuffix(".md")
        resp = await client.delete(f"/api/memories/{slug}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_delete_memory_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete("/api/memories/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_streams_agent_events(app):
    """Chat endpoint streams typed SSE events from AgentLoop."""

    async def mock_run(self):
        yield TextDelta(content="Hello ")
        yield TextDelta(content="world")
        yield Finished(usage=UsageStats(
            prompt_tokens=10, completion_tokens=5, total_tokens=15, elapsed_seconds=0.5
        ))

    with patch("web.backend.server.AgentLoop.run", mock_run):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "hi"}],
                "model": "test/model",
            })

    assert resp.status_code == 200
    lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
    payloads = [json.loads(l.removeprefix("data: ")) for l in lines]

    text_events = [p for p in payloads if p.get("type") == "text"]
    assert len(text_events) == 2
    assert text_events[0]["content"] == "Hello "
    assert text_events[1]["content"] == "world"

    done_events = [p for p in payloads if p.get("type") == "done"]
    assert len(done_events) == 1
    assert done_events[0]["usage"]["total_tokens"] == 15


@pytest.mark.asyncio
async def test_chat_streams_tool_events(app):
    """Chat endpoint streams tool_call and tool_result SSE events."""

    async def mock_run(self):
        yield ToolCallStart(id="call_1", name="web_search", arguments={"query": "news"})
        yield ToolResult(id="call_1", name="web_search", output="1. Breaking news\n   https://example.com", is_error=False)
        yield TextDelta(content="Here's the latest news.")
        yield Finished(usage=UsageStats(
            prompt_tokens=30, completion_tokens=15, total_tokens=45, elapsed_seconds=1.2
        ))

    with patch("web.backend.server.AgentLoop.run", mock_run):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "what's in the news?"}],
                "model": "test/model",
            })

    assert resp.status_code == 200
    lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
    payloads = [json.loads(l.removeprefix("data: ")) for l in lines]

    tool_calls = [p for p in payloads if p.get("type") == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "web_search"
    assert tool_calls[0]["arguments"] == {"query": "news"}

    tool_results = [p for p in payloads if p.get("type") == "tool_result"]
    assert len(tool_results) == 1
    assert "Breaking news" in tool_results[0]["output"]
    assert tool_results[0]["is_error"] is False

    text_events = [p for p in payloads if p.get("type") == "text"]
    assert text_events[0]["content"] == "Here's the latest news."
