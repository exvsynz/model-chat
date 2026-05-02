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
