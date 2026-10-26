"""Tests for account registration, meal logging, and daily progress."""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

# Tests use SQLite, so no Neon credentials are needed.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("BASE_AUTH_URL", "http://localhost")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
import main
from routers import auth_helpers, meals, profiles

TEST_USER = auth_helpers.local_user_id("test-better-auth-user")


@pytest.fixture
def api_client():
    # Each test gets a fresh database so meals do not carry into other tests.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    database.Base.metadata.create_all(engine)
    original_engine = database.engine
    database.engine = engine
    sessions = sessionmaker(bind=engine)

    def get_test_db():
        with sessions() as session:
            yield session

    async def get_test_user():
        return TEST_USER

    main.app.dependency_overrides[auth_helpers.get_db] = get_test_db
    main.app.dependency_overrides[auth_helpers.current_user] = get_test_user

    with sessions() as db:
        db.add(database.Profiles(
            user_id=TEST_USER, first_name="Test", is_premium=False, is_active=True
        ))
        db.commit()

    try:
        with TestClient(main.app) as client:
            yield client, sessions
    finally:
        main.app.dependency_overrides.clear()
        database.engine = original_engine
        engine.dispose()


def sample_meal(**changes):
    data = {
        "food_name": "Chicken bowl", "calories": 600, "protein": 50,
        "carbs": 30, "cholesterol": 25, "trans_fats": 0,
        "saturated_fats": 3, "total_fats": 10,
    }
    data.update(changes)
    return data


def sample_goal(user_id=TEST_USER, **changes):
    day = datetime.now(timezone.utc).date()
    data = {
        "user_id": user_id, "effective_date": day, "calories": 2000,
        "protein": 100, "carbs": -1, "cholesterol": 300,
        "trans_fats": 0, "saturated_fats": 20, "total_fats": 80,
    }
    data.update(changes)
    return database.Goals(**data)


def test_meal_logging_and_progress(api_client):
    client, sessions = api_client
    with sessions() as db:
        db.add(sample_goal())
        db.commit()

    saved = client.post("/meals", json=sample_meal())
    assert saved.status_code == 201, saved.text
    assert saved.json()["meal_id"] > 0
    assert saved.json()["consumed_at"]

    listing = client.get("/meals/today")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    progress = client.get("/progress/today")
    assert progress.status_code == 200
    values = progress.json()["nutrients"]
    assert values["calories"]["percentage"] == 30
    assert values["protein"]["percentage"] == 50
    assert values["carbs"]["status"] == "not_set"
    assert values["trans_fats"]["status"] == "at"


def test_invalid_meals_do_not_get_saved(api_client):
    client, _ = api_client
    assert client.post("/meals", json=sample_meal(fiber=10)).status_code == 422
    assert client.post("/meals", json=sample_meal(calories=-1)).status_code == 422
    assert client.post("/meals", json=sample_meal(food_name="   ")).status_code == 422
    assert client.get("/meals/today").json() == []


def test_old_meals_do_not_count_today(api_client):
    client, sessions = api_client
    with sessions() as db:
        db.add(database.Meals(
            user_id=TEST_USER,
            consumed_at=datetime.now(timezone.utc) - timedelta(days=4),
            **sample_meal(),
        ))
        db.commit()
    assert client.get("/meals/today").json() == []
    assert client.get("/progress/today").json()["nutrients"]["calories"]["consumed"] == 0


def test_only_the_current_users_meals_are_visible(api_client):
    client, sessions = api_client
    with sessions() as db:
        db.add(database.Meals(
            user_id=uuid.uuid4(), consumed_at=datetime.now(timezone.utc), **sample_meal()
        ))
        db.commit()
    assert client.get("/meals/today").json() == []


def test_latest_active_goal_is_used(api_client):
    client, sessions = api_client
    today = datetime.now(timezone.utc).date()
    with sessions() as db:
        db.add(sample_goal(effective_date=today - timedelta(days=2), calories=1500))
        db.add(sample_goal(effective_date=today, calories=2000))
        db.add(sample_goal(effective_date=today + timedelta(days=2), calories=5000))
        db.commit()
    goal = client.get("/progress/today").json()["nutrients"]["calories"]
    assert goal["goal"] == 2000


def test_unset_goals_are_not_complete(api_client):
    client, sessions = api_client
    with sessions() as db:
        db.add(sample_goal(protein=-1))
        db.commit()
    result = client.get("/progress/today").json()["nutrients"]["protein"]
    assert result["percentage"] is None
    assert result["met"] is False


def test_registration_saves_profile_without_password(api_client, monkeypatch):
    client, sessions = api_client

    async def fake_auth(method, route, *, payload=None, cookies=None):
        assert method == "POST" and route == "sign-up/email"
        assert payload["password"] == "new-test-password"
        return Mock(headers=httpx.Headers()), {"user": {"id": "new-auth-user"}}

    monkeypatch.setattr(profiles, "auth_request", fake_auth)
    response = client.post("/auth/register", json={
        "name": "Taylor Gator", "email": "taylor@example.com",
        "password": "new-test-password",
    })
    assert response.status_code == 201, response.text
    with sessions() as db:
        profile = db.get(database.Profiles, auth_helpers.local_user_id("new-auth-user"))
        assert profile.first_name == "Taylor"
        assert not hasattr(profile, "password")


def test_bad_registration_never_calls_auth(api_client, monkeypatch):
    client, _ = api_client

    async def should_not_call(*args, **kwargs):
        pytest.fail("Invalid registration should not reach Better Auth")

    monkeypatch.setattr(profiles, "auth_request", should_not_call)
    response = client.post("/auth/register", json={
        "name": "Test", "email": "not-an-email", "password": "123",
    })
    assert response.status_code == 422


def test_missing_session_is_rejected(monkeypatch):
    # Test this without the authentication override from the other tests.
    async def should_not_call(*args, **kwargs):
        pytest.fail("No cookie should not call Better Auth")

    monkeypatch.setattr(auth_helpers, "auth_request", should_not_call)
    with TestClient(main.app) as client:
        response = client.get("/meals/today")
    assert response.status_code == 401
