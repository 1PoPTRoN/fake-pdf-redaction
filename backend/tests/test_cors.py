"""CORS allow-list is configurable via env, not a hardcoded wildcard."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client_with_env(monkeypatch, value: str | None) -> TestClient:
    if value is None:
        monkeypatch.delenv("PDFAUDIT_CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("PDFAUDIT_CORS_ORIGINS", value)
    from app.main import create_app

    return TestClient(create_app())


def test_cors_reflects_allowed_origin_from_env(monkeypatch):
    client = _client_with_env(monkeypatch, "https://allowed.example")
    r = client.get("/api/v1/health", headers={"origin": "https://allowed.example"})
    assert r.headers.get("access-control-allow-origin") == "https://allowed.example"


def test_cors_does_not_reflect_disallowed_origin(monkeypatch):
    client = _client_with_env(monkeypatch, "https://allowed.example")
    r = client.get("/api/v1/health", headers={"origin": "https://evil.example"})
    aco = r.headers.get("access-control-allow-origin")
    assert aco != "https://evil.example"
    assert aco != "*"  # must not be an open wildcard


def test_cors_default_is_localhost_not_wildcard(monkeypatch):
    client = _client_with_env(monkeypatch, None)
    r = client.get("/api/v1/health", headers={"origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-origin") != "*"
