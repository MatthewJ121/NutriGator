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
    assert any(cookie.startswith(cookie_name + "=") and "Max-Age=0" in cookie for cookie in response.headers.get_list("set-cookie"))


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


@pytest.mark.parametrize("upstream_name", ["__Secure-neon-auth.session_token", "__Secure-better-auth.session_token", "session_token"])
def test_login_cookie_survives_local_proxy_and_validates_with_neon(monkeypatch, upstream_name):
    from routers import auth_helpers
    from fastapi import Depends
    from fastapi import FastAPI
    from starlette.responses import Response
    from starlette.requests import Request
    import uuid

    app = FastAPI()
    signed_value = "signed-test-session-token"
    @app.post("/login")
    def login(request: Request):
        response = Response()
        upstream = httpx.Response(200, headers={"set-cookie":
            f"{upstream_name}={signed_value}; Domain=neonauth.example; Path=/neondb/auth; Secure; HttpOnly; SameSite=None; Partitioned"})
        auth_helpers.copy_session_cookie(upstream, response, request)
        return response
    @app.get("/protected")
    def protected(user=Depends(auth_helpers.current_user)):
        return {"user_id": str(user)}

    async def fake_session(method, route, *, payload=None, cookies=None):
        assert method == "GET" and route == "get-session"
        assert cookies == {upstream_name: signed_value}
        return httpx.Response(200), {"user": {"id": "real-auth-user"}}
    monkeypatch.setattr(auth_helpers, "auth_request", fake_session)
    with TestClient(app, base_url="http://localhost:8000") as client:
        result = client.post("/login")
        cookie = result.headers["set-cookie"]
        assert "Domain=" not in cookie
        assert "Partitioned" not in cookie
        assert "SameSite=lax" in cookie and "HttpOnly" in cookie
        assert "Secure" not in cookie
        assert "Path=/;" in cookie
        assert result.cookies.get(auth_helpers.local_cookie_name(upstream_name)) == signed_value
        result = client.get("/protected")
        assert result.status_code == 200
        assert uuid.UUID(result.json()["user_id"]) == auth_helpers.local_user_id("real-auth-user")


def test_https_cookie_remains_secure_and_host_scoped():
    from routers import auth_helpers
    from fastapi import Request, Response
    request = Request({"type":"http", "scheme":"https", "server":("app.example",443), "path":"/auth/login", "headers":[]})
    response = Response()
    auth_helpers.copy_session_cookie(httpx.Response(200,headers={"set-cookie":"__Secure-neon-auth.session_token=signed; Domain=neon.example; Path=/auth; Secure; SameSite=None; Partitioned"}),response,request)
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Secure-neon-auth.session_token=")
    assert "Secure" in cookie and "HttpOnly" in cookie
    assert "SameSite=lax" in cookie and "Domain=" not in cookie
