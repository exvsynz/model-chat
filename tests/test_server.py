import logging

import pytest
from httpx import AsyncClient, ASGITransport
from web.backend.server import create_app


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
