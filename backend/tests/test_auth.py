"""Register → login → /me flow."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_login_me(client: AsyncClient) -> None:
    creds = {"email": "alice@example.com", "password": "supersecret"}

    # Register
    r = await client.post("/auth/register", json=creds)
    assert r.status_code == 201, r.text
    user = r.json()
    assert user["email"] == creds["email"]
    assert "id" in user

    # Duplicate register → 409
    r2 = await client.post("/auth/register", json=creds)
    assert r2.status_code == 409

    # Login
    r3 = await client.post("/auth/login", json=creds)
    assert r3.status_code == 200, r3.text
    token = r3.json()["access_token"]
    assert token

    # /me with valid token
    r4 = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r4.status_code == 200
    assert r4.json()["email"] == creds["email"]

    # /me without token → 401
    r5 = await client.get("/auth/me")
    assert r5.status_code == 401

    # Wrong password → 401
    r6 = await client.post("/auth/login", json={**creds, "password": "wrong"})
    assert r6.status_code == 401


@pytest.mark.asyncio
async def test_register_validates_email_and_password_length(client: AsyncClient) -> None:
    r = await client.post("/auth/register", json={"email": "not-an-email", "password": "longenough"})
    assert r.status_code == 422

    r = await client.post("/auth/register", json={"email": "bob@example.com", "password": "short"})
    assert r.status_code == 422
