import sys
from pathlib import Path
from datetime import date, datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import database
import main

TEST_USER = main.local_user_id("example-better-auth-user")

@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def db_override():
        with sessions() as session:
            yield session

    async def user_override():
        return TEST_USER

    main.app.dependency_overrides[main.get_db] = db_override
    main.app.dependency_overrides[main.current_user] = user_override
    with sessions() as db:
        db.add(database.Profile(user_id=TEST_USER, first_name="Sam", is_premium=False, is_active=True))
        db.add(database.Goals(user_id=TEST_USER, effective_date=date.today(), calories=2000, protein=100,
            carbs=-1, cholesterol=300, trans_fats=0, saturated_fats=20, total_fats=80))
        db.commit()
    yield TestClient(main.app), sessions
    main.app.dependency_overrides.clear()
    engine.dispose()


def meal(**changes):
    data = {"food_name": "Chicken bowl", "calories": 600, "protein": 50,
            "carbs": 30, "cholesterol": 25, "trans_fats": 0,
            "saturated_fats": 3, "total_fats": 10}
    data.update(changes)
    return data


def test_add_meal_and_progress(client):
    api, _ = client
    response = api.post("/meals", json=meal())
    assert response.status_code == 201, response.text
    assert response.json()["meal_id"] > 0
    listing = api.get("/meals/today")
    assert len(listing.json()) == 1
    progress = api.get("/progress/today").json()["nutrients"]
    assert progress["calories"]["percentage"] == 30
    assert progress["protein"]["percentage"] == 50
    assert progress["carbs"]["status"] == "not_set"
    assert progress["trans_fats"]["status"] == "at"


def test_bad_category_and_negative_numbers_do_not_save(client):
    api, _ = client
    assert api.post("/meals", json=meal(fiber=50)).status_code == 422
    assert api.post("/meals", json=meal(calories=-2)).status_code == 422
    assert api.post("/meals", json=meal(food_name="   ")).status_code == 422
    assert api.get("/meals/today").json() == []


def test_other_day_is_not_counted(client):
    api, sessions = client
    with sessions() as db:
        db.add(database.Meals(user_id=TEST_USER, consumed_at=datetime(2020, 1, 1, tzinfo=timezone.utc), **meal()))
        db.commit()
    assert api.get("/progress/today").json()["nutrients"]["calories"]["consumed"] == 0


def test_cannot_use_other_users_data(client):
    api, sessions = client
    with sessions() as db:
        db.add(database.Meals(user_id=main.local_user_id("someone-else"), **meal()))
        db.commit()
    assert api.get("/meals/today").json() == []


def test_blank_goals_are_not_counted_as_completed(client):
    api, sessions = client
    with sessions() as db:
        goals = db.scalars(select(database.Goals).where(database.Goals.user_id == TEST_USER)).first()
        goals.protein = -1
        db.commit()
    result = api.get("/progress/today").json()["nutrients"]["protein"]
    assert result["percentage"] is None
    assert result["met"] is False


def test_registration_saves_profile_and_keeps_password_out_of_database(client, monkeypatch):
    from unittest.mock import Mock

    api, sessions = client

    async def signup(method, route, *, payload=None, cookies=None):
        assert method == "POST"
        assert route == "sign-up/email"
        assert payload["password"] == "safe-pass-123"
        return Mock(headers=httpx.Headers()), {"user": {"id": "new-user-id"}}

    import httpx
    monkeypatch.setattr(main, "auth_request", signup)
    response = api.post("/auth/register", json={
        "name": "Taylor Gator", "email": "taylor@example.com", "password": "safe-pass-123"
    })
    assert response.status_code == 201, response.text
    with sessions() as db:
        profile = db.get(database.Profile, main.local_user_id("new-user-id"))
        assert profile.first_name == "Taylor"
        assert not hasattr(profile, "password")


def test_registration_rejects_invalid_input_without_calling_provider(client, monkeypatch):
    api, _ = client

    async def do_not_call(*args, **kwargs):
        pytest.fail("Invalid data should not reach Better Auth")

    monkeypatch.setattr(main, "auth_request", do_not_call)
    assert api.post("/auth/register", json={
        "name": "A", "email": "not-email", "password": "123"
    }).status_code == 422


def test_latest_applicable_goal_is_used(client):
    api, sessions = client
    with sessions() as db:
        db.add(database.Goals(
            user_id=TEST_USER, effective_date=date.today() - timedelta(days=1),
            calories=1500, protein=120, carbs=-1, cholesterol=-1,
            trans_fats=-1, saturated_fats=-1, total_fats=-1
        ))
        db.add(database.Goals(
            user_id=TEST_USER, effective_date=date.today() + timedelta(days=1),
            calories=5000, protein=120, carbs=-1, cholesterol=-1,
            trans_fats=-1, saturated_fats=-1, total_fats=-1
        ))
        db.commit()
    # Today's goal still wins; future changes should not apply yet.
    progress = api.get("/progress/today").json()["nutrients"]
    assert progress["calories"]["goal"] == 2000
