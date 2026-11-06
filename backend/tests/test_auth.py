import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("BASE_AUTH_URL", "http://localhost")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
import routers.profiles as profiles


@pytest.mark.parametrize(
    "cookie_name,cookie_value",
    [("better-auth.session_token", "session-value")],
)
def test_logout_calls_auth_service_and_clears_session_cookie(
    monkeypatch, cookie_name, cookie_value
):
    captured = {}
    expired_cookie = (
        "better-auth.session_token=; Path=/; Max-Age=0; HttpOnly"
    )

    async def fake_auth_request(method, route, *, payload=None, cookies=None):
        captured.update(
            method=method,
            route=route,
            payload=payload,
            cookies=dict(cookies or {}),
        )
        return (
            httpx.Response(
                200,
                json={"success": True},
                headers={"set-cookie": expired_cookie},
            ),
            {"success": True},
        )

    monkeypatch.setattr(profiles, "auth_request", fake_auth_request)

    with TestClient(main.app) as client:
        response = client.post(
            "/auth/logout",
            cookies={cookie_name: cookie_value},
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Logged out"}
    assert captured == {
        "method": "POST",
        "route": "sign-out",
        "payload": {},
        "cookies": {cookie_name: cookie_value},
    }
    assert expired_cookie in response.headers.get_list("set-cookie")


def test_logout_clears_session_cookie_when_auth_service_fails(monkeypatch):
    async def failing_auth_request(method, route, *, payload=None, cookies=None):
        raise HTTPException(502, "Authentication service returned an error")

    monkeypatch.setattr(profiles, "auth_request", failing_auth_request)

    with TestClient(main.app) as client:
        response = client.post(
            "/auth/logout",
            cookies={"better-auth.session_token": "session-value"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Authentication service returned an error"
    assert any(
        cookie.startswith("better-auth.session_token=")
        and "Max-Age=0" in cookie
        for cookie in response.headers.get_list("set-cookie")
    )
