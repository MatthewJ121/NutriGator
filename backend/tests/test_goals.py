import os
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("BASE_AUTH_URL", "http://localhost")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
import main

'''Test infastructure'''
@pytest.fixture
def api_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.Base.metadata.create_all(engine)
    original_engine = getattr(database, "engine", None)
    database.engine = engine

    with TestClient(main.app) as client:
        yield client, sessionmaker(bind=engine)

    database.engine = original_engine
    engine.dispose()


def create_profile(session_factory, user_id=None):
    user_id = user_id or uuid.uuid4()
    with session_factory() as session:
        session.add(
            database.Profiles(
                user_id=user_id,
                first_name="Test",
                is_premium=False,
                is_active=True,
            )
        )
        session.commit()
    return user_id


def make_goal_payload(**overrides):
    payload = {
        "effective_date": str(date.today()),
        "calories": 2200,
        "protein": 150,
        "carbs": 250,
        "cholesterol": 300,
        "trans_fats": 0,
        "saturated_fats": 20,
        "total_fats": 70
    }
    payload.update(overrides)
    return payload


'''Test Cases'''
def test_goal_set_valid_creates_goal_returns_201(api_client):
    client, session_factory = api_client
    user_id = create_profile(session_factory)

    response = client.post(
        f"/api/goals/{user_id}",
        json=make_goal_payload(calories=2100.5),
    )

    assert response.status_code == 201, response.text
    assert response.json()["message"] == "Goal created successfully"

    fetched = client.get(f"/api/goals/{user_id}")
    assert fetched.status_code == 200, fetched.text
    goals = fetched.json()["goals"]
    assert len(goals) == 1
    assert goals[0]["calories"] == 2100.5
    assert goals[0]["protein"] == 150


def test_goal_set_invalid_goal_input_retuns_422(api_client):
    client, session_factory = api_client
    user_id = create_profile(session_factory)

    response = client.post(
        f"/api/goals/{user_id}",
        json=make_goal_payload(protein="Twenty"),
    )

    assert response.status_code == 422, response.text

    fetched = client.get(f"/api/goals/{user_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["goals"] == []


def test_goal_set_invalid_user_id_returns_404(api_client):
    client, _ = api_client
    fake_user_id = uuid.uuid4()

    response = client.post(
        f"/api/goals/{fake_user_id}",
        json=make_goal_payload(),
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "User not found"


def test_goal_set_duplicate_date_returns_409(api_client):
    client, session_factory = api_client
    user_id = create_profile(session_factory)
    payload = make_goal_payload()

    first = client.post(f"/api/goals/{user_id}", json=payload)
    second = client.post(f"/api/goals/{user_id}", json=payload)

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert second.json()["detail"] == "Goal for this date and user exists, use PUT instead"


def test_goal_set_invalid_category_input_returns_422(api_client):
    client, session_factory = api_client
    user_id = create_profile(session_factory)

    payload = {
        "calories": 2100,
        "carbs": 250,
        "sugar": 15,
        "total_fats": 12.4
    }

    response = client.post(
        f"/api/goals/{user_id}",
        json=payload
    )

    assert response.status_code == 422

def test_goal_change_valid_returns_200(api_client):
    client, session_factory = api_client
    user_id = create_profile(session_factory)
    goal_date = date.today()

    with session_factory() as session:
        session.add(
            database.Goals(
                user_id=user_id,
                effective_date=goal_date,
                calories=2000,
                protein=20,
                carbs=250,
                cholesterol=300,
                trans_fats=0,
                saturated_fats=20,
                total_fats=70,
            )
        )
        session.commit()

    response = client.put(
        f"/api/goals/{user_id}",
        json=make_goal_payload(effective_date=str(goal_date), protein=40),
    )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Goal updated successfully"

    fetched = client.get(f"/api/goals/{user_id}")
    assert fetched.status_code == 200, fetched.text
    saved_goal = fetched.json()["goals"][0]
    assert saved_goal["protein"] == 40
    assert saved_goal["calories"] == 2200


def test_goal_change_invalid_goal_input_returns_422(api_client):
    client, session_factory = api_client
    user_id = create_profile(session_factory)
    goal_date = date.today()

    with session_factory() as session:
        session.add(
            database.Goals(
                user_id=user_id,
                effective_date=goal_date,
                calories=2000,
                protein=20,
                carbs=250,
                cholesterol=300,
                trans_fats=0,
                saturated_fats=20,
                total_fats=70,
            )
        )
        session.commit()

    response = client.put(
        f"/api/goals/{user_id}",
        json=make_goal_payload(effective_date=str(goal_date), protein="Twenty"),
    )

    assert response.status_code == 422, response.text

    fetched = client.get(f"/api/goals/{user_id}")
    assert fetched.status_code == 200, fetched.text
    saved_goal = fetched.json()["goals"][0]
    assert saved_goal["protein"] == 20


def test_goal_update_invalid_user_id_returns_404(api_client):
    client, _ = api_client
    fake_user_id = uuid.uuid4()

    response = client.put(
        f"/api/goals/{fake_user_id}",
        json=make_goal_payload(),
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "User not found"


def test_goal_get_invalid_user_id_returns_404(api_client):
    client, _ = api_client
    fake_user_id = uuid.uuid4()

    response = client.get(f"/api/goals/{fake_user_id}")

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "User not found"


def test_goal_view_valid_user_id_returns_200(api_client):
    client, session_factory = api_client
    user_id = create_profile(session_factory)
    today = date.today()

    with session_factory() as session:
        session.add(
            database.Goals(
                user_id=user_id,
                effective_date=today,
                calories=2200,
                protein=150,
                carbs=250,
                cholesterol=300,
                trans_fats=0,
                saturated_fats=20,
                total_fats=70,
            )
        )
        session.commit()

    response = client.get(f"/api/goals/{user_id}")

    assert response.status_code == 200, response.text
    goals = response.json()["goals"]
    assert len(goals) == 1
    assert goals[0]["calories"] == 2200
    assert goals[0]["protein"] == 150
    assert goals[0]["carbs"] == 250