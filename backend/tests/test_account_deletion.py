"""Tests for Issue #10: deactivating an account without deleting its records."""
import os
import sys
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("BASE_AUTH_URL", "http://localhost")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import database
import main
from routers import auth_helpers, profiles

USER = auth_helpers.local_user_id("delete-account-test-user")
COOKIE = {"better-auth.session_token": "test-signed-session"}
URL = "/api/profiles/auth/delete"


@pytest.fixture
def api_client():
    # Give each test a clean database. Nothing here reaches Neon.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    original = main.app.dependency_overrides.copy()

    def test_db():
        with sessions() as db:
            yield db

    async def test_user():
        return USER

    main.app.dependency_overrides[auth_helpers.get_db] = test_db
    main.app.dependency_overrides[auth_helpers.current_user] = test_user
    with sessions() as db:
        db.add(database.Profiles(user_id=USER, first_name="Student", is_premium=False, is_active=True))
        db.commit()
    try:
        with TestClient(main.app) as client:
            yield client, sessions
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(original)
        engine.dispose()


def mock_auth(monkeypatch, *, verified=True):
    calls = []

    async def fake_auth(method, route, *, payload=None, cookies=None):
        calls.append((method, route, payload, cookies))
        if route == "verify-password":
            if not verified:
                from fastapi import HTTPException
                raise HTTPException(401, "Invalid password")
            return httpx.Response(200), {"status": True}
        if route == "sign-out":
            return httpx.Response(200), {"success": True}
        pytest.fail(f"Unexpected auth endpoint: {route}")

    monkeypatch.setattr(profiles, "auth_request", fake_auth)
    return calls


def test_deactivation_keeps_profile_and_clears_session(api_client, monkeypatch):
    client, sessions = api_client
    calls = mock_auth(monkeypatch)
    response = client.request("DELETE", URL, json={"password": "correct-password"}, cookies=COOKIE)
    assert response.status_code == 200, response.text
    assert response.json() == {"message": "Account deactivated"}
    assert calls[0] == ("POST", "verify-password", {"password": "correct-password"}, COOKIE)
    assert calls[1][:2] == ("POST", "sign-out")
    assert any("Max-Age=0" in value for value in response.headers.get_list("set-cookie"))
    with sessions() as db:
        profile = db.get(database.Profiles, USER)
        assert profile is not None and profile.is_active is False


def test_wrong_password_returns_403_without_deactivation(api_client, monkeypatch):
    client, sessions = api_client
    calls = mock_auth(monkeypatch, verified=False)
    response = client.request("DELETE", URL, json={"password": "wrong"}, cookies=COOKIE)
    assert response.status_code == 403
    assert response.json()["detail"] == "Incorrect password"
    assert len(calls) == 1
    with sessions() as db:
        assert db.get(database.Profiles, USER).is_active is True


def test_expired_session_returns_401_before_password_check(api_client, monkeypatch):
    client, sessions = api_client
    main.app.dependency_overrides.pop(auth_helpers.current_user)

    async def expired_session(*args, **kwargs):
        return Mock(), {"user": None, "session": None}

    monkeypatch.setattr(auth_helpers, "auth_request", expired_session)
    calls = mock_auth(monkeypatch)
    response = client.request("DELETE", URL, json={"password": "correct-password"}, cookies=COOKIE)
    assert response.status_code == 401
    assert calls == []
    with sessions() as db:
        assert db.get(database.Profiles, USER).is_active is True


def test_missing_session_is_401(api_client, monkeypatch):
    client, _ = api_client
    main.app.dependency_overrides.pop(auth_helpers.current_user)
    calls = mock_auth(monkeypatch)
    response = client.request("DELETE", URL, json={"password": "correct-password"})
    assert response.status_code == 401
    assert calls == []


def test_inactive_account_cannot_deactivate_again(api_client, monkeypatch):
    client, sessions = api_client
    with sessions() as db:
        db.get(database.Profiles, USER).is_active = False
        db.commit()
    calls = mock_auth(monkeypatch)
    response = client.request("DELETE", URL, json={"password": "correct-password"}, cookies=COOKIE)
    assert response.status_code == 403
    assert calls == []


def test_database_failure_rolls_back(api_client, monkeypatch):
    client, sessions = api_client
    mock_auth(monkeypatch)

    def fail_commit(self):
        raise SQLAlchemyError("test database problem")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = client.request("DELETE", URL, json={"password": "correct-password"}, cookies=COOKIE)
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to deactivate account"}
    with sessions() as db:
        assert db.get(database.Profiles, USER).is_active is True


def test_false_password_verification_is_rejected(api_client, monkeypatch):
    client, sessions = api_client
    async def fake_auth(method, route, *, payload=None, cookies=None):
        return httpx.Response(200), {"status": False}
    monkeypatch.setattr(profiles, "auth_request", fake_auth)
    response = client.request("DELETE", URL, json={"password": "wrong"}, cookies=COOKIE)
    assert response.status_code == 403
    with sessions() as db:
        assert db.get(database.Profiles, USER).is_active is True


def test_missing_profile_returns_401(api_client, monkeypatch):
    client, sessions = api_client
    with sessions() as db:
        db.delete(db.get(database.Profiles, USER))
        db.commit()
    calls = mock_auth(monkeypatch)
    response = client.request("DELETE", URL, json={"password": "correct-password"}, cookies=COOKIE)
    assert response.status_code == 401
    assert calls == []


def test_sign_out_failure_still_deactivates_and_clears_cookie(api_client, monkeypatch):
    client, sessions = api_client
    from fastapi import HTTPException
    async def fake_auth(method, route, *, payload=None, cookies=None):
        if route == "sign-out":
            raise HTTPException(502, "Auth unavailable")
        return httpx.Response(200), {"status": True}
    monkeypatch.setattr(profiles, "auth_request", fake_auth)
    response = client.request("DELETE", URL, json={"password": "correct-password"}, cookies=COOKIE)
    assert response.status_code == 200
    assert any("Max-Age=0" in value for value in response.headers.get_list("set-cookie"))
    with sessions() as db:
        assert db.get(database.Profiles, USER).is_active is False
