"""Tests for getting and changing a user's premium status."""
import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("BASE_AUTH_URL", "http://localhost")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import database
import main
from routers import auth_helpers

USER_ID = auth_helpers.local_user_id("premium-test-user")


@pytest.fixture
def premium_client():
    # Each test starts with its own small database.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    previous = main.app.dependency_overrides.copy()

    def test_db():
        with sessions() as db:
            yield db

    async def test_user():
        return USER_ID

    main.app.dependency_overrides[auth_helpers.get_db] = test_db
    main.app.dependency_overrides[auth_helpers.current_user] = test_user
    with sessions() as db:
        db.add(database.Profiles(
            user_id=USER_ID, first_name="Premium", is_premium=False, is_active=True
        ))
        db.commit()

    try:
        with TestClient(main.app) as client:
            yield client, sessions
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous)
        engine.dispose()


def premium_value(sessions):
    with sessions() as db:
        return db.get(database.Profiles, USER_ID).is_premium


def test_enable_premium(premium_client):
    client, sessions = premium_client
    response = client.put("/api/profiles/premium", json={"state": True})
    assert response.status_code == 200
    assert response.json() == {"message": "Premium status updated", "status": True}
    assert premium_value(sessions) is True


def test_enable_premium_twice_returns_204(premium_client):
    client, sessions = premium_client
    assert client.put("/api/profiles/premium", json={"state": True}).status_code == 200
    response = client.put("/api/profiles/premium", json={"state": True})
    assert response.status_code == 204 and response.content == b""
    assert premium_value(sessions) is True


def test_disable_when_already_free_returns_204(premium_client):
    client, sessions = premium_client
    response = client.put("/api/profiles/premium", json={"state": False})
    assert response.status_code == 204 and response.content == b""
    assert premium_value(sessions) is False


def test_disable_premium(premium_client):
    client, sessions = premium_client
    assert client.put("/api/profiles/premium", json={"state": True}).status_code == 200
    response = client.put("/api/profiles/premium", json={"state": False})
    assert response.status_code == 200
    assert response.json()["status"] is False
    assert premium_value(sessions) is False


def test_get_free_status_without_changes(premium_client):
    client, sessions = premium_client
    response = client.get("/api/profiles/premium")
    assert response.status_code == 200
    assert response.json() == {"status": False}
    assert premium_value(sessions) is False


def test_get_premium_status_without_changes(premium_client):
    client, sessions = premium_client
    client.put("/api/profiles/premium", json={"state": True})
    response = client.get("/api/profiles/premium")
    assert response.status_code == 200
    assert response.json() == {"status": True}
    assert premium_value(sessions) is True


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_inactive_account_is_blocked(premium_client, method):
    client, sessions = premium_client
    with sessions() as db:
        db.get(database.Profiles, USER_ID).is_active = False
        db.commit()
    response = client.request(method, "/api/profiles/premium", json={"state": True} if method == "PUT" else None)
    assert response.status_code == 403
    assert premium_value(sessions) is False


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_invalid_session_is_rejected(premium_client, method):
    client, sessions = premium_client
    main.app.dependency_overrides.pop(auth_helpers.current_user)
    response = client.request(method, "/api/profiles/premium", json={"state": True} if method == "PUT" else None)
    assert response.status_code == 401
    assert premium_value(sessions) is False


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_unknown_profile_returns_404(premium_client, method):
    client, sessions = premium_client
    with sessions() as db:
        db.delete(db.get(database.Profiles, USER_ID))
        db.commit()
    response = client.request(method, "/api/profiles/premium", json={"state": True} if method == "PUT" else None)
    assert response.status_code == 404


@pytest.mark.parametrize("invalid", ["true", 1, None, {}])
def test_invalid_state_returns_422_without_changes(premium_client, invalid):
    client, sessions = premium_client
    response = client.put("/api/profiles/premium", json={"state": invalid})
    assert response.status_code == 422
    assert premium_value(sessions) is False


def test_update_database_failure_returns_500_and_rolls_back(premium_client, monkeypatch):
    client, sessions = premium_client

    def fail_commit(self):
        raise SQLAlchemyError("Simulated commit failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = client.put("/api/profiles/premium", json={"state": True})
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to update premium status"}
    assert premium_value(sessions) is False


def test_get_database_failure_returns_500(premium_client, monkeypatch):
    client, _ = premium_client

    def fail_read(self, model, user_id, *args, **kwargs):
        raise SQLAlchemyError("Simulated read failure")

    monkeypatch.setattr(Session, "get", fail_read)
    response = client.get("/api/profiles/premium")
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to read premium status"}


def test_different_user_cannot_change_other_profile(premium_client):
    client, sessions = premium_client
    other_id = uuid.uuid4()
    with sessions() as db:
        db.add(database.Profiles(user_id=other_id, first_name="Other", is_premium=False, is_active=True))
        db.commit()
    response = client.put("/api/profiles/premium", json={"state": True, "user_id": str(other_id)})
    # The requested user_id isn't used. Only the authenticated user can be changed.
    assert response.status_code == 200
    with sessions() as db:
        assert db.get(database.Profiles, USER_ID).is_premium is True
        assert db.get(database.Profiles, other_id).is_premium is False
