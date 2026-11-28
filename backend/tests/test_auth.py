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
from sqlalchemy.exc import OperationalError

import main
from routers import auth_helpers, profiles


def allow_password_update(monkeypatch):
    async def current_user():
        return auth_helpers.local_user_id("password-update-test-user")

    monkeypatch.setitem(
        main.app.dependency_overrides,
        auth_helpers.current_user,
        current_user,
    )
    monkeypatch.setattr(profiles, "require_active_profile", lambda user_id, db: None)


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
            "/api/profiles/auth/logout",
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
            "/api/profiles/auth/logout",
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
    request = Request({"type":"http", "scheme":"https", "server":("app.example",443), "path":"/api/profiles/auth/login", "headers":[]})
    response = Response()
    auth_helpers.copy_session_cookie(httpx.Response(200,headers={"set-cookie":"__Secure-neon-auth.session_token=signed; Domain=neon.example; Path=/auth; Secure; SameSite=None; Partitioned"}),response,request)
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Secure-neon-auth.session_token=")
    assert "Secure" in cookie and "HttpOnly" in cookie
    assert "SameSite=lax" in cookie and "Domain=" not in cookie


def test_https_cookie_can_use_cross_site_policy(monkeypatch):
    from fastapi import Request, Response
    from routers import auth_helpers

    monkeypatch.setenv("AUTH_COOKIE_SAMESITE", "none")
    request = Request({
        "type": "http",
        "scheme": "https",
        "server": ("api.example.com", 443),
        "path": "/api/profiles/auth/login",
        "headers": [],
    })
    response = Response()

    auth_helpers.copy_session_cookie(
        httpx.Response(
            200,
            headers={"set-cookie": "session_token=signed; Path=/; HttpOnly"},
        ),
        response,
        request,
    )

    cookie = response.headers["set-cookie"]
    assert "SameSite=none" in cookie
    assert "Secure" in cookie


def test_login_returns_service_unavailable_when_profile_database_is_down(monkeypatch):
    async def fake_auth_request(method, route, *, payload=None, cookies=None):
        assert method == "POST" and route == "sign-in/email"
        return httpx.Response(200), {"user": {"id": "test-auth-user"}}

    def unavailable_profile(user_id, db):
        raise OperationalError("SELECT profile", {}, OSError("database unavailable"))

    monkeypatch.setattr(profiles, "auth_request", fake_auth_request)
    monkeypatch.setattr(profiles, "require_active_profile", unavailable_profile)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/auth/login",
            json={"email": "user@example.com", "password": "valid-password"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Profile database is unavailable; login could not be completed"
    }


def test_forgot_password_requests_reset_link(monkeypatch):
    captured = {}

    async def fake_auth_request(method, route, *, payload=None, cookies=None):
        captured.update(method=method, route=route, payload=payload)
        return httpx.Response(200), {"status": True}

    monkeypatch.setattr(profiles, "auth_request", fake_auth_request)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/password/forgot",
            json={"email": "user@example.com"},
        )

    assert response.status_code == 200
    assert response.json() is None
    assert captured == {
        "method": "POST",
        "route": "request-password-reset",
        "payload": {"email": "user@example.com"},
    }


def test_forgot_password_hides_auth_client_errors(monkeypatch):
    async def fake_auth_request(method, route, *, payload=None, cookies=None):
        raise HTTPException(404, "User not found")

    monkeypatch.setattr(profiles, "auth_request", fake_auth_request)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/password/forgot",
            json={"email": "missing@example.com"},
        )

    assert response.status_code == 200
    assert response.json() is None


def test_forgot_password_returns_service_error(monkeypatch):
    async def fake_auth_request(method, route, *, payload=None, cookies=None):
        raise HTTPException(502, "Authentication service is unavailable")

    monkeypatch.setattr(profiles, "auth_request", fake_auth_request)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/password/forgot",
            json={"email": "user@example.com"},
        )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Authentication service is unavailable"
    }


def test_reset_password_calls_auth_service(monkeypatch):
    captured = {}

    async def fake_auth_request(method, route, *, payload=None, cookies=None):
        captured.update(method=method, route=route, payload=payload)
        return httpx.Response(200), {"status": True}

    monkeypatch.setattr(profiles, "auth_request", fake_auth_request)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/password/reset",
            json={
                "token": "valid-reset-token",
                "newPassword": "new-password",
            },
        )

    assert response.status_code == 200
    assert response.json() is None
    assert captured == {
        "method": "POST",
        "route": "reset-password",
        "payload": {
            "token": "valid-reset-token",
            "newPassword": "new-password",
        },
    }


@pytest.mark.parametrize(
    "status_code,detail",
    [
        (400, "Invalid or expired reset token"),
        (422, "Password does not meet requirements"),
        (502, "Authentication service is unavailable"),
    ],
)
def test_reset_password_propagates_auth_errors(
    monkeypatch, status_code, detail
):
    async def fake_auth_request(method, route, *, payload=None, cookies=None):
        raise HTTPException(status_code, detail)

    monkeypatch.setattr(profiles, "auth_request", fake_auth_request)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/password/reset",
            json={
                "token": "reset-token",
                "newPassword": "new-password",
            },
        )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_update_password_calls_auth_service_with_session_cookies(monkeypatch):
    captured = {}
    auth_session = {}
    monkeypatch.setattr(
        profiles, "require_active_profile", lambda profile_id, db: None
    )

    async def successful_session_lookup(method, route, *, payload=None, cookies=None):
        auth_session.update(
            method=method,
            route=route,
            cookies=dict(cookies or {}),
        )
        return httpx.Response(200), {"user": {"id": "password-update-test-user"}}

    async def fake_auth_request(method, route, *, payload=None, cookies=None):
        captured.update(
            method=method,
            route=route,
            payload=payload,
            cookies=dict(cookies or {}),
        )
        return httpx.Response(200), {"status": True}

    monkeypatch.setattr(auth_helpers, "auth_request", successful_session_lookup)
    monkeypatch.setattr(profiles, "auth_request", fake_auth_request)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/password/update",
            cookies={"better-auth.session_token": "session-value"},
            json={
                "current1": "old-password",
                "current2": "old-password",
                "new": "new-password",
            },
        )

    assert response.status_code == 200
    assert response.json() is None
    assert auth_session == {
        "method": "GET",
        "route": "get-session",
        "cookies": {"better-auth.session_token": "session-value"},
    }
    assert captured == {
        "method": "POST",
        "route": "change-password",
        "payload": {
            "currentPassword": "old-password",
            "newPassword": "new-password",
        },
        "cookies": {"better-auth.session_token": "session-value"},
    }


def test_update_password_rejects_mismatched_current_passwords(monkeypatch):
    allow_password_update(monkeypatch)

    async def unexpected_auth_request(method, route, *, payload=None, cookies=None):
        pytest.fail("Authentication service should not be called")

    monkeypatch.setattr(profiles, "auth_request", unexpected_auth_request)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/password/update",
            cookies={"better-auth.session_token": "session-value"},
            json={
                "current1": "old-password",
                "current2": "different-password",
                "new": "new-password",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Current password confirmations do not match"


def test_update_password_requires_session():
    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/password/update",
            json={
                "current1": "old-password",
                "current2": "old-password",
                "new": "new-password",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Please log in first"


def test_update_password_rejects_invalid_session_cookie(monkeypatch):
    async def invalid_session(method, route, *, payload=None, cookies=None):
        assert method == "GET" and route == "get-session"
        assert cookies == {"better-auth.session_token": "invalid-session"}
        raise HTTPException(401, "Please log in first")

    async def unexpected_password_change(
        method, route, *, payload=None, cookies=None
    ):
        pytest.fail("Password change must not run for an invalid session")

    monkeypatch.setattr(auth_helpers, "auth_request", invalid_session)
    monkeypatch.setattr(profiles, "auth_request", unexpected_password_change)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/password/update",
            cookies={"better-auth.session_token": "invalid-session"},
            json={
                "current1": "old-password",
                "current2": "old-password",
                "new": "new-password",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Please log in first"


@pytest.mark.parametrize(
    "status_code,detail",
    [
        (401, "Please log in first"),
        (403, "Current password is incorrect"),
        (422, "Password does not meet requirements"),
        (502, "Authentication service is unavailable"),
    ],
)
def test_update_password_propagates_auth_errors(monkeypatch, status_code, detail):
    allow_password_update(monkeypatch)

    async def fake_auth_request(method, route, *, payload=None, cookies=None):
        raise HTTPException(status_code, detail)

    monkeypatch.setattr(profiles, "auth_request", fake_auth_request)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/profiles/password/update",
            cookies={"better-auth.session_token": "session-value"},
            json={
                "current1": "old-password",
                "current2": "old-password",
                "new": "new-password",
            },
        )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
