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
    response = client.post("/api/profiles/auth/register", json={
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
    response = client.post("/api/profiles/auth/register", json={
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


def test_meal_edit_untrack_delete_and_day_boundaries(api_client):
    client, _ = api_client
    payload = {"food_name": "Toast", "consumed_at": "2026-11-10T23:30:00-05:00", "protein": 0, "calories": 120.5}
    saved = client.post("/api/meals", json=payload)
    assert saved.status_code == 200, saved.text
    meal = saved.json()
    assert meal["protein"] == 0 and meal["carbs"] == -1
    url = "/api/meals/2026-11-10?timezone_offset=300"
    assert len(client.get(url).json()) == 1
    assert client.get("/api/meals/2026-11-11?timezone_offset=300").status_code == 204
    edited = client.post("/api/meals", json={"meal_id": meal["meal_id"], "food_name": "New toast", "consumed_at": "2026-11-09T12:00:00Z", "protein": 0})
    assert edited.status_code == 200, edited.text
    assert edited.json()["calories"] == -1
    assert client.get(url).status_code == 204
    assert client.get("/api/meals/2026-11-09").json()[0]["food_name"] == "New toast"
    assert client.request("DELETE", "/api/meals", json={"meal_id": meal["meal_id"]}).status_code == 204
    assert client.get("/api/meals/2026-11-09").status_code == 204


def test_new_meal_api_validates_and_checks_ownership(api_client):
    client, sessions = api_client
    payload = {"food_name": "Toast", "consumed_at": "2026-11-10T12:00:00Z"}
    for change in ({"calories": -1}, {"calories": "abc"}, {"sugar": 1}, {"food_name": "  "}, {"consumed_at": "2026-11-10T12:00:00"}):
        assert client.post("/api/meals", json={**payload, **change}).status_code == 422
    with sessions() as db:
        meal = database.Meals(user_id=uuid.uuid4(), consumed_at=datetime.now(timezone.utc), **sample_meal())
        db.add(meal)
        db.commit()
        meal_id = meal.meal_id
    assert client.post("/api/meals", json={**payload, "meal_id": meal_id}).status_code == 404
    assert client.request("DELETE", "/api/meals", json={"meal_id": meal_id}).status_code == 403


def test_day_listing_is_sorted_and_handles_dst(api_client):
    client, _ = api_client
    for when in ["2026-11-01T23:30:00-05:00", "2026-11-01T00:30:00-04:00", "2026-11-02T00:00:00-05:00"]:
        assert client.post("/api/meals", json={"food_name": "Toast", "consumed_at": when}).status_code == 200
    rows = client.get("/api/meals/2026-11-01?timezone_offset=240&timezone_end_offset=300").json()
    assert len(rows) == 2
    assert rows[0]["consumed_at"] < rows[1]["consumed_at"]


def test_delete_by_id_permissions_and_inactive_account(api_client):
    client, sessions = api_client
    own = client.post("/api/meals", json={"food_name": "Toast", "consumed_at": "2026-11-10T12:00:00Z"}).json()["meal_id"]
    with sessions() as db:
        other = database.Meals(user_id=uuid.uuid4(), consumed_at=datetime.now(timezone.utc), **sample_meal())
        db.add(other)
        db.commit()
        other_id = other.meal_id
    response = client.delete(f"/api/meals/{other_id}")
    assert response.status_code == 403
    assert "food_name" not in response.json()
    assert client.delete("/api/meals/999999").status_code == 404
    with sessions() as db:
        db.get(database.Profiles, TEST_USER).is_active = False
        db.commit()
    assert client.delete(f"/api/meals/{own}").status_code == 403
    with sessions() as db:
        assert db.get(database.Meals, own) is not None
        db.get(database.Profiles, TEST_USER).is_active = True
        db.commit()
    assert client.delete(f"/api/meals/{own}").status_code == 204
    with sessions() as db:
        assert db.get(database.Meals, own) is None
        assert db.get(database.Meals, other_id) is not None


def test_delete_rejects_inactive_session(api_client, monkeypatch):
    client, _ = api_client
    main.app.dependency_overrides.pop(auth_helpers.current_user)
    async def expired_session(*args, **kwargs):
        return Mock(), {"user": None, "session": None}
    monkeypatch.setattr(auth_helpers, "auth_request", expired_session)
    client.cookies.set("session", "expired")
    assert client.delete("/api/meals/1").status_code == 401


def test_delete_database_failure_rolls_back(api_client, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    client, sessions = api_client
    meal_id = client.post("/api/meals", json={"food_name": "Toast", "consumed_at": "2026-11-10T12:00:00Z"}).json()["meal_id"]
    def failed_commit(self):
        raise SQLAlchemyError("Database failure")
    monkeypatch.setattr(Session, "commit", failed_commit)
    response = client.delete(f"/api/meals/{meal_id}")
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to delete meal"}
    with sessions() as db:
        assert db.get(database.Meals, meal_id) is not None


def test_history_contract_empty_invalid_inactive_and_progress(api_client):
    client, sessions = api_client
    for prefix in ("/api/meals", "/api/progress"):
        assert client.get(f"{prefix}/not-a-date").status_code == 422
        assert client.get(f"{prefix}/2026-02-30").status_code == 422
        empty = client.get(f"{prefix}/2026-11-01")
        assert empty.status_code == 204 and empty.content == b""
        assert empty.headers["x-detail"] == "No data on 2026-11-01"
    with sessions() as db:
        db.add(sample_goal(effective_date=datetime(2026, 10, 1).date(), calories=200))
        db.add(sample_goal(effective_date=datetime(2026, 12, 1).date(), calories=999))
        db.commit()
    for when, calories in [("2026-11-01T12:00:00Z", 50), ("2026-11-02T12:00:00Z", 90)]:
        client.post("/api/meals", json={"food_name": "Meal", "consumed_at": when, "calories": calories})
    response = client.get("/api/progress/2026-11-01")
    assert response.status_code == 200
    progress = response.json()
    assert progress["date"] == "2026-11-01"
    assert progress["nutrients"]["calories"]["consumed"] == 50
    assert progress["nutrients"]["calories"]["goal"] == 200
    assert progress["nutrients"]["protein"]["consumed"] == 0
    with sessions() as db:
        db.get(database.Profiles, TEST_USER).is_active = False
        db.commit()
    for path in ("/api/meals/2026-11-01", "/api/progress/2026-11-01"):
        assert client.get(path).status_code == 403


def test_all_meal_history_endpoints_require_session(api_client):
    client, _ = api_client
    main.app.dependency_overrides.pop(auth_helpers.current_user)
    assert client.get("/api/meals/2026-11-01").status_code == 401
    assert client.get("/api/progress/2026-11-01").status_code == 401
    assert client.post("/api/meals", json={"food_name": "Test", "consumed_at": "2026-11-01T12:00:00Z"}).status_code == 401
    assert client.delete("/api/meals/1").status_code == 401


def test_meal_section_is_independent_of_timestamp_and_survives_edits(api_client):
    client, _ = api_client
    body = {"food_name": "Late breakfast", "meal_type": "breakfast", "consumed_at": "2026-11-12T14:37:00-05:00", "calories": 100}
    saved = client.post("/api/meals", json=body).json()
    assert saved["consumed_at"] == "2026-11-12T19:37:00+00:00"
    assert saved["meal_type"] == "breakfast"
    rows = client.get("/api/meals/2026-11-12?timezone_offset=300").json()
    assert rows[0]["meal_type"] == "breakfast"
    edited = client.post("/api/meals", json={"meal_id": saved["meal_id"], "food_name": "Edited breakfast", "consumed_at": "2026-11-12T15:09:00-05:00"}).json()
    assert edited["meal_type"] == "breakfast"
    assert edited["consumed_at"] == "2026-11-12T20:09:00+00:00"
    assert client.post("/api/meals", json={**body, "meal_type": "custom"}).status_code == 422
