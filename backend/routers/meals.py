"""Saving meals and checking daily progress."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

import database
from routers.auth_helpers import DB, UserId

router = APIRouter(tags=["Meals and Progress"])

NUTRIENTS = (
    "calories", "protein", "carbs", "cholesterol",
    "trans_fats", "saturated_fats", "total_fats",
)


class MealRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_name: str = Field(min_length=1, max_length=200)
    calories: float = Field(ge=0, allow_inf_nan=False)
    protein: float = Field(ge=0, allow_inf_nan=False)
    carbs: float = Field(ge=0, allow_inf_nan=False)
    cholesterol: float = Field(ge=0, allow_inf_nan=False)
    trans_fats: float = Field(ge=0, allow_inf_nan=False)
    saturated_fats: float = Field(ge=0, allow_inf_nan=False)
    total_fats: float = Field(ge=0, allow_inf_nan=False)


def meal_data(meal: database.Meals):
    return {
        "meal_id": meal.meal_id,
        "food_name": meal.food_name,
        "consumed_at": meal.consumed_at.isoformat(),
        **{field: float(getattr(meal, field)) for field in NUTRIENTS},
    }


def utc_day():
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


@router.post("/meals", status_code=201)
def add_meal(body: MealRequest, user_id: UserId, db: DB):
    profile = db.get(database.Profiles, user_id)
    if not profile or not profile.is_active:
        raise HTTPException(403, "This account is not active")

    if not body.food_name.strip():
        raise HTTPException(422, "Food name cannot be blank")

    # Save this meal under the currently logged-in user.
    meal = database.Meals(
        user_id=user_id,
        food_name=body.food_name.strip(),
        consumed_at=datetime.now(timezone.utc),
        **{field: getattr(body, field) for field in NUTRIENTS},
    )
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return meal_data(meal)


@router.get("/meals/today")
def todays_meals(user_id: UserId, db: DB):
    start, end = utc_day()
    meals = db.scalars(
        select(database.Meals).where(
            database.Meals.user_id == user_id,
            database.Meals.consumed_at >= start,
            database.Meals.consumed_at < end,
        ).order_by(database.Meals.consumed_at)
    ).all()
    return [meal_data(meal) for meal in meals]

@router.delete("/meals/{target_meal_id}", status_code=501) #TODO change status to 204 when implemented
def delete_meal(target_meal_id: int, user_id: UserId, db: DB):
    """
    Delete a nutrition goal for a user. No request body is required.

    Parameters:  
        target_meal_id (int): ID of the meal to delete.  

    Returns:  
        None.

    Raises:  
        HTTPException(401): Invalid session.  
        HTTPException(403): Logged-in user does not own this meal.  
        HTTPException(404): The meal does not exist.  
        HTTPException(500): The database delete failed.
    """
pass


@router.get("/progress/today")
def today_progress(user_id: UserId, db: DB):
    start, end = utc_day()
    totals_row = db.execute(
        select(*[
            func.coalesce(func.sum(getattr(database.Meals, key)), 0).label(key)
            for key in NUTRIENTS
        ]).where(
            database.Meals.user_id == user_id,
            database.Meals.consumed_at >= start,
            database.Meals.consumed_at < end,
        )
    ).one()

    # The newest goal effective today or earlier is the one we use.
    goals = db.scalars(
        select(database.Goals).where(
            database.Goals.user_id == user_id,
            database.Goals.effective_date <= start.date(),
        ).order_by(
            database.Goals.effective_date.desc(),
            database.Goals.goal_id.desc(),
        ).limit(1)
    ).first()

    progress = {}
    for field, total in zip(NUTRIENTS, totals_row):
        consumed = float(total)
        target = getattr(goals, field) if goals else None
        if target is None or target < 0:
            progress[field] = {
                "consumed": consumed, "goal": None, "percentage": None,
                "status": "not_set", "met": False,
            }
            continue

        # A zero target has no meaningful percentage when consumption is positive.
        percentage = round(consumed / target * 100, 1) if target > 0 else (100.0 if consumed == 0 else None)
        position = "below" if consumed < target else ("at" if consumed == target else "above")
        progress[field] = {
            "consumed": consumed, "goal": float(target),
            "percentage": percentage, "status": position,
            "met": consumed >= target,
        }

    return {"date": start.date().isoformat(), "timezone": "UTC", "nutrients": progress}

@router.get("/history", status_code=501)
def meal_history(user_id: UserId, db: DB):
    """
    Retrieve the entire meal history for a user. No request body is accepted.

    Parameters:  
        None.

    Returns:  
        dict: List of all meal info keyed by consumption date.
        message: Details the length of the returned dictionary and success message.

    Raises:  
        HTTPException(401): Invalid session or user.     
        HTTPException(403): Inactive user.
        HTTPException(500): The database read failed.
"""
pass