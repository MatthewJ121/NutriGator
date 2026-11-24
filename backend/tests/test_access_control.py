"""Access-control coverage for authenticated meals, goals, and login."""
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("BASE_AUTH_URL", "http://localhost")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
import main
from routers import auth_helpers, profiles

AUTH_ID = "access-control-user"
USER_ID = auth_helpers.local_user_id(AUTH_ID)
OTHER_USER_ID = uuid.uuid4()


@pytest.fixture
def api_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.Base.metadata.create_all(engine)
    original_engine = database.engine
    original_overrides = main.app.dependency_overrides.copy()
    database.engine = engine
    sessions = sessionmaker(bind=engine)

    def get_test_db():
        with sessions() as session:
            yield session

    async def current_user():
        return USER_ID

    main.app.dependency_overrides[auth_helpers.get_db] = get_test_db
    main.app.dependency_overrides[auth_helpers.current_user] = current_user
    with sessions() as session:
        session.add_all([
            database.Profiles(
                user_id=USER_ID,
                first_name="Current",
                is_premium=False,
                is_active=True,
            ),
            database.Profiles(
                user_id=OTHER_USER_ID,
                first_name="Other",
                is_premium=False,
                is_active=True,
            ),
        ])
        session.commit()

    try:
        with TestClient(main.app) as client:
            yield client, sessions
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(original_overrides)
        database.engine = original_engine
        engine.dispose()


def goal_payload(**changes):
    payload = {
        "effective_date": str(date.today()),
        "calories": 2000,
        "protein": 100,
        "carbs": 200,
        "cholesterol": 300,
        "trans_fats": 0,
        "saturated_fats": 20,
        "total_fats": 80,
    }
    payload.update(changes)
    return payload


def meal_payload(**changes):
    payload = {
        "food_name": "Test meal",
        "consumed_at": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(changes)
    return payload


def test_successful_login_rejects_inactive_profile(api_client, monkeypatch):
    client, sessions = api_client
    with sessions() as session:
        session.get(database.Profiles, USER_ID).is_active = False
        session.commit()

    async def successful_auth(method, route, *, payload=None, cookies=None):
        assert method == "POST"
        assert route == "sign-in/email"
        return httpx.Response(200), {
            "user": {"id": AUTH_ID, "email": "current@example.com"}
        }

    monkeypatch.setattr(profiles, "auth_request", successful_auth)
    response = client.post(
        "/api/profiles/auth/login",
        json={"email": "current@example.com", "password": "valid-password"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "This account is not active"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/meals/2026-01-15", None),
        ("POST", "/api/meals", meal_payload()),
        ("GET", "/api/progress/2026-01-15", None),
        ("POST", "/api/goals", goal_payload()),
        ("PUT", "/api/goals", goal_payload()),
        ("GET", "/api/goals", None),
        ("DELETE", "/api/goals/2026-01-15", None),
        ("GET", "/meals/today", None),
        ("GET", "/progress/today", None),
    ],
)
def test_inactive_profile_is_rejected_by_data_routes(api_client, method, path, body):
    client, sessions = api_client
    with sessions() as session:
        session.get(database.Profiles, USER_ID).is_active = False
        session.commit()

    response = client.request(method, path, json=body)

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "This account is not active"


def test_authenticated_reads_and_writes_are_scoped_to_session_user(api_client):
    client, sessions = api_client
    today = date.today()
    now = datetime.combine(today, time(hour=12))
    other_goal_date = today - timedelta(days=1)
    with sessions() as session:
        session.add_all([
            database.Meals(
                user_id=USER_ID,
                consumed_at=now,
                food_name="My meal",
                meal_type="lunch",
                calories=300,
                protein=20,
                carbs=30,
                cholesterol=10,
                trans_fats=0,
                saturated_fats=2,
                total_fats=5,
            ),
            database.Meals(
                user_id=OTHER_USER_ID,
                consumed_at=now,
                food_name="Other meal",
                meal_type="lunch",
                calories=900,
                protein=60,
                carbs=90,
                cholesterol=30,
                trans_fats=0,
                saturated_fats=6,
                total_fats=15,
            ),
            database.Goals(
                user_id=USER_ID,
                effective_date=today,
                calories=2000,
                protein=100,
                carbs=200,
                cholesterol=300,
                trans_fats=0,
                saturated_fats=20,
                total_fats=80,
            ),
            database.Goals(
                user_id=OTHER_USER_ID,
                effective_date=other_goal_date,
                calories=5000,
                protein=500,
                carbs=500,
                cholesterol=500,
                trans_fats=0,
                saturated_fats=50,
                total_fats=50,
            ),
        ])
        session.commit()
        other_meal_id = session.query(database.Meals).filter_by(
            user_id=OTHER_USER_ID
        ).one().meal_id

    meals_response = client.get(
        f"/api/meals/{today}", params={"user_id": str(OTHER_USER_ID)}
    )
    assert meals_response.status_code == 200
    assert [meal["food_name"] for meal in meals_response.json()] == ["My meal"]

    goals_response = client.get(
        "/api/goals", params={"user_id": str(OTHER_USER_ID)}
    )
    assert goals_response.status_code == 200
    assert [goal["user_id"] for goal in goals_response.json()["goals"]] == [
        str(USER_ID)
    ]

    progress_response = client.get(
        f"/api/progress/{today}", params={"user_id": str(OTHER_USER_ID)}
    )
    assert progress_response.status_code == 200
    assert progress_response.json()["nutrients"]["calories"]["consumed"] == 300

    forged_goal = client.post(
        "/api/goals",
        json=goal_payload(user_id=str(OTHER_USER_ID), effective_date="2026-02-01"),
    )
    assert forged_goal.status_code == 422

    forged_meal = client.post(
        "/api/meals",
        json=meal_payload(user_id=str(OTHER_USER_ID)),
    )
    assert forged_meal.status_code == 422

    foreign_meal_edit = client.post(
        "/api/meals",
        json=meal_payload(meal_id=other_meal_id),
    )
    assert foreign_meal_edit.status_code == 404

    foreign_goal_update = client.put(
        "/api/goals",
        json=goal_payload(effective_date=str(other_goal_date)),
    )
    assert foreign_goal_update.status_code == 404

    foreign_goal_delete = client.delete(f"/api/goals/{other_goal_date}")
    assert foreign_goal_delete.status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/meals/2026-01-15", None),
        ("POST", "/api/meals", meal_payload()),
        ("GET", "/api/progress/2026-01-15", None),
        ("POST", "/api/goals", goal_payload()),
        ("PUT", "/api/goals", goal_payload()),
        ("GET", "/api/goals", None),
        ("DELETE", "/api/goals/2026-01-15", None),
        ("GET", "/meals/today", None),
        ("POST", "/meals", {
            "food_name": "Test meal",
            "calories": 100,
            "protein": 10,
            "carbs": 10,
            "cholesterol": 10,
            "trans_fats": 0,
            "saturated_fats": 1,
            "total_fats": 2,
        }),
        ("GET", "/progress/today", None),
    ],
)
def test_data_routes_reject_invalid_session(api_client, method, path, body):
    client, _ = api_client
    main.app.dependency_overrides.pop(auth_helpers.current_user)

    response = client.request(method, path, json=body)

    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Please log in first"