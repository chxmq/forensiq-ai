"""Auth and security tests."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token, verify_access_token
from app.core.config import get_settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_token_roundtrip():
    token = create_access_token("tester")
    assert verify_access_token(token) == "tester"


def test_health_is_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_applications_require_auth_when_enabled(monkeypatch):
    monkeypatch.setenv("FORENSIQ_AUTH_ENABLED", "true")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.get("/api/applications")
    assert r.status_code == 401
    get_settings.cache_clear()


def test_login_and_access(client, monkeypatch):
    monkeypatch.setenv("FORENSIQ_AUTH_ENABLED", "true")
    monkeypatch.setenv("FORENSIQ_AUTH_USERNAME", "underwriter")
    monkeypatch.setenv("FORENSIQ_AUTH_PASSWORD", "forensiq")
    get_settings.cache_clear()
    c = TestClient(app)
    bad = c.post("/api/auth/login", json={"username": "baduser", "password": "wrongpass"})
    assert bad.status_code == 401
    ok = c.post("/api/auth/login", json={"username": "underwriter", "password": "forensiq"})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    apps = c.get("/api/applications", headers={"Authorization": f"Bearer {token}"})
    assert apps.status_code == 200
    get_settings.cache_clear()
