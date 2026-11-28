"""Tests for the all-dates meal history endpoint (Issue #45)."""
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("BASE_AUTH_URL", "http://localhost")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import database
import main
from routers import auth_helpers

USER_ID = auth_helpers.local_user_id("history-test-user")


@pytest.fixture
def client_and_db():
    # This uses a fresh SQLite database, not our team's Neon database.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def test_db():
        with sessions() as db:
            yield db

    async def test_user():
        return USER_ID

    main.app.dependency_overrides[auth_helpers.get_db] = test_db
    main.app.dependency_overrides[auth_helpers.current_user] = test_user
    with sessions() as db:
        db.add(database.Profiles(user_id=USER_ID, first_name="History", is_active=True, is_premium=False))
        db.commit()
    try:
        with TestClient(main.app) as client:
            yield client, sessions
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()


def add_meal(sessions, when, *, owner=USER_ID, food="Rice bowl", calories=450):
    with sessions() as db:
        meal = database.Meals(
            user_id=owner, consumed_at=datetime.fromisoformat(when), food_name=food,
            meal_type="lunch", calories=calories, protein=22, carbs=60,
            cholesterol=10, trans_fats=0, saturated_fats=2, total_fats=12,
        )
        db.add(meal)
        db.commit()
        db.refresh(meal)
        return meal.meal_id


def test_empty_history_returns_204_with_no_body(client_and_db):
    client, _ = client_and_db
    response = client.get("/api/meals/history")
    assert response.status_code == 204
    assert response.content == b""


def test_multiple_meals_same_day_keep_all_fields(client_and_db):
    client, sessions = client_and_db
    a = add_meal(sessions, "2026-11-10T09:00:00", food="Breakfast", calories=300)
    b = add_meal(sessions, "2026-11-10T12:00:00", food="Lunch")
    result = client.get("/api/meals/history")
    assert result.status_code == 200, result.text
    body = result.json()
    assert list(body["history"]) == ["2026-11-10"]
    items = body["history"]["2026-11-10"]
    assert [item["meal_id"] for item in items] == [a, b]
    assert [item["food_name"] for item in items] == ["Breakfast", "Lunch"]
    assert items[0]["calories"] == 300
    assert items[0]["protein"] == 22
    assert items[0]["meal_type"] == "lunch"
    assert items[0]["consumed_at"].startswith("2026-11-10T09:00:00")
    assert "2 meals" in body["message"]


def test_history_groups_different_days_in_order(client_and_db):
    client, sessions = client_and_db
    add_meal(sessions, "2026-11-12T08:00:00")
    add_meal(sessions, "2026-11-11T08:00:00")
    add_meal(sessions, "2026-11-12T19:00:00")
    response = client.get("/api/meals/history")
    assert response.status_code == 200
    assert list(response.json()["history"]) == ["2026-11-11", "2026-11-12"]
    assert [len(v) for v in response.json()["history"].values()] == [1, 2]


def test_does_not_show_another_users_meals(client_and_db):
    client, sessions = client_and_db
    add_meal(sessions, "2026-11-10T08:00:00", owner=uuid.uuid4())
    assert client.get("/api/meals/history").status_code == 204


def test_inactive_profile_gets_403(client_and_db):
    client, sessions = client_and_db
    with sessions() as db:
        db.get(database.Profiles, USER_ID).is_active = False
        db.commit()
    response = client.get("/api/meals/history")
    assert response.status_code == 403


def test_invalid_session_gets_401(client_and_db):
    client, _ = client_and_db
    main.app.dependency_overrides.pop(auth_helpers.current_user)
    response = client.get("/api/meals/history")
    assert response.status_code == 401


def test_history_does_not_modify_meals(client_and_db):
    client, sessions = client_and_db
    meal_id = add_meal(sessions, "2026-11-10T08:00:00")
    with sessions() as db:
        before = [(m.meal_id, m.food_name, m.calories) for m in db.scalars(select(database.Meals)).all()]
    assert client.get("/api/meals/history").status_code == 200
    assert client.get("/api/meals/history").status_code == 200
    with sessions() as db:
        after = [(m.meal_id, m.food_name, m.calories) for m in db.scalars(select(database.Meals)).all()]
    assert before == after
    assert before[0][0] == meal_id


def test_database_read_error_returns_500(client_and_db, monkeypatch):
    client, sessions = client_and_db
    add_meal(sessions, "2026-11-10T08:00:00")
    original_scalars = Session.scalars

    def broken_read(self, statement, *args, **kwargs):
        if "Meals" in str(statement):
            raise SQLAlchemyError("Test database read failure")
        return original_scalars(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "scalars", broken_read)
    response = client.get("/api/meals/history")
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to load meal history"}
