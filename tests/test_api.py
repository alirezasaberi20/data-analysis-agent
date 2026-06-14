"""Tests for the FastAPI endpoints."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_check(client):
    async with client as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_sessions_empty(client):
    async with client as ac:
        response = await ac.get("/api/sessions")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_nonexistent_session(client):
    async with client as ac:
        response = await ac.get("/api/sessions/fake-id/history")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_session(client):
    async with client as ac:
        response = await ac.delete("/api/sessions/fake-id")
    assert response.status_code == 404
