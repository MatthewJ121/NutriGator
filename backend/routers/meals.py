"""
Handles all API requests related to meals and nutrition progress.

URL Prefix:
    /api/meals and /api/progress

Endpoints:
    POST /api/meals - Add a meal or replace an existing meal's tracked values.
    GET /api/meals/{day} - List the authenticated user's meals for a local date.
    DELETE /api/meals/{target_meal_id} - Delete an owned meal without a body.
    DELETE /api/meals - Compatibility route accepting a meal_id body.
    GET /api/progress/{day} - Calculate nutrition progress for a local date.
    POST /meals, GET /meals/today, GET /progress/today - Legacy routes.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError

import database
from routers.auth_helpers import DB, UserId

router = APIRouter(prefix="/api/meals", tags=["Meals"])
progress_router = APIRouter(prefix="/api/progress", tags=["Progress"])
legacy_router = APIRouter(tags=["Legacy meals and progress"])


def require_active_profile(user_id, db):
    profile = db.get(database.Profiles, user_id)
    if not profile or not profile.is_active:
        raise HTTPException(403, "This account is not active")


def day_bounds(day, start_offset=0, end_offset=None):
    start = datetime.combine(day, datetime.min.time()) + timedelta(minutes=start_offset)
    end = datetime.combine(day + timedelta(days=1), datetime.min.time()) + timedelta(
        minutes=start_offset if end_offset is None else end_offset)
    return start, end


def no_data_response(day):
    # HTTP 204 cannot contain JSON. The frontend treats it as an empty list.
    return Response(status_code=204, headers={"X-Detail": f"No data on {day.isoformat()}"})


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


class MealSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_id: int | None = Field(default=None, gt=0)
    food_name: str = Field(min_length=1, max_length=200)
    consumed_at: datetime
    meal_type: Literal["breakfast", "lunch", "dinner", "snacks"] | None = None
    calories: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    protein: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    carbs: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cholesterol: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    trans_fats: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    saturated_fats: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    total_fats: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class MealDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_id: int = Field(gt=0)


def owned_meal(meal_id, user_id, db):
    meal = db.get(database.Meals, meal_id)
    if not meal or meal.user_id != user_id:
        raise HTTPException(404, "Meal not found")
    return meal


@router.post("")
def save_meal(body: MealSaveRequest, user_id: UserId, db: DB):
    """Save a meal, replacing all tracked nutrients on edit.

    Args:
        body: Food, timezone-aware consumed_at, optional meal_id and nutrients.
            Omit nutrients to untrack them; zero is tracked.
        user_id: User derived from the authenticated session.
        db: Database session.

    Returns:
        dict: The saved meal, including ID and UTC timestamp.

    Raises:
        HTTPException(401): Invalid session.
        HTTPException(403): Inactive account.
        HTTPException(404): Missing or unowned meal.
        HTTPException(422): Invalid food, time, category, or nutrient value.
    """
    require_active_profile(user_id, db)
    if not body.food_name.strip():
        raise HTTPException(422, "Food name cannot be blank")
    if body.consumed_at.tzinfo is None:
        raise HTTPException(422, "Meal time must include a timezone")
    if body.meal_id is not None:
        meal = owned_meal(body.meal_id, user_id, db)
    else:
        meal = database.Meals(user_id=user_id)
        db.add(meal)
    meal.food_name = body.food_name.strip()
    if body.meal_type is not None:
        meal.meal_type = body.meal_type
    # Store UTC without an offset, matching the existing database schema.
    meal.consumed_at = body.consumed_at.astimezone(timezone.utc).replace(tzinfo=None)
    for field in NUTRIENTS:
        value = getattr(body, field)
        setattr(meal, field, -1 if value is None else value)
    db.commit()
    db.refresh(meal)
    return meal_data(meal)


def delete_owned_meal(meal_id, user_id, db):
    require_active_profile(user_id, db)
    meal = db.get(database.Meals, meal_id)
    if meal is None:
        raise HTTPException(404, "Meal not found")
    if meal.user_id != user_id:
        raise HTTPException(403, "You do not own this meal")
    try:
        db.delete(meal)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(500, "Unable to delete meal") from exc


@router.delete("/{target_meal_id}", status_code=204)
def delete_meal(target_meal_id: int, user_id: UserId, db: DB):
    """Delete an owned meal. No request body is required.

    Args:
        target_meal_id: ID of the meal to delete.
        user_id: User derived from the authenticated session.
        db: Database session.

    Returns:
        None: HTTP 204 after successful deletion.

    Raises:
        HTTPException(401): Invalid session.
        HTTPException(403): Inactive account or unowned meal.
        HTTPException(404): Meal does not exist.
        HTTPException(500): Database deletion failed.
    """
    delete_owned_meal(target_meal_id, user_id, db)


# Keep the body-based route used by the earlier daily-log specification.
@router.delete("", status_code=204)
def delete_meal_body(body: MealDeleteRequest, user_id: UserId, db: DB):
    """Delete a meal through the legacy body-based contract.

    Args:
        body: Contains meal_id; other fields are rejected.

    Returns:
        None: HTTP 204 on success.

    Raises:
        HTTPException: Uses the same 401/403/404/500 contract as delete_meal.
    """
    delete_owned_meal(body.meal_id, user_id, db)


@router.get("/{day}")
def meals_for_day(day: date, user_id: UserId, db: DB,
                  timezone_offset: int = Query(default=0, ge=-840, le=840),
                  timezone_end_offset: int | None = Query(default=None, ge=-840, le=840)):
    """List this session user's meals chronologically for a calendar date.

    Args:
        day: Selected local date, YYYY-MM-DD.
        timezone_offset: Minutes from the local day start to UTC.
        timezone_end_offset: Minutes from the next day start to UTC.

    Returns:
        list: Owned meals in time order, or 204 with X-Detail for an empty date.

    Raises:
        HTTPException(401): Invalid session.
        HTTPException(403): Inactive account.
        HTTPException(422): Invalid date or timezone offset.
    """
    require_active_profile(user_id, db)
    start, end = day_bounds(day, timezone_offset, timezone_end_offset)
    rows = db.scalars(select(database.Meals).where(
        database.Meals.user_id == user_id,
        database.Meals.consumed_at >= start,
        database.Meals.consumed_at < end,
    ).order_by(database.Meals.consumed_at, database.Meals.meal_id)).all()
    return [meal_data(meal) for meal in rows] if rows else no_data_response(day)


def meal_data(meal: database.Meals):
    return {
        "meal_id": meal.meal_id,
        "food_name": meal.food_name,
        "meal_type": meal.meal_type,
        "consumed_at": meal.consumed_at.replace(tzinfo=timezone.utc).isoformat(),
        **{field: float(getattr(meal, field)) for field in NUTRIENTS},
    }


def utc_day():
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


@legacy_router.post("/meals", status_code=201)
def add_meal(body: MealRequest, user_id: UserId, db: DB):
    require_active_profile(user_id, db)

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


@legacy_router.get("/meals/today")
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


@legacy_router.get("/progress/today")
def today_progress(user_id: UserId, db: DB):
    start, end = utc_day()
    return calculate_progress(start, end, start.date(), user_id, db)


@progress_router.get("/{day}")
def progress_for_day(day: date, user_id: UserId, db: DB,
                     timezone_offset: int = Query(default=0, ge=-840, le=840),
                     timezone_end_offset: int | None = Query(default=None, ge=-840, le=840)):
    """Calculate progress for a date using meals and goals owned by the session user.

    Args:
        day: Local calendar date in YYYY-MM-DD form.
        timezone_offset: Minutes from local midnight to UTC.
        timezone_end_offset: Offset at the next midnight, including DST changes.

    Returns:
        dict: Totals and applicable goals, or 204 with X-Detail when no meals exist.

    Raises:
        HTTPException(401): Invalid session.
        HTTPException(403): Inactive account.
        HTTPException(422): Invalid date or offset.
    """
    require_active_profile(user_id, db)
    start, end = day_bounds(day, timezone_offset, timezone_end_offset)
    exists = db.scalar(select(database.Meals.meal_id).where(
        database.Meals.user_id == user_id,
        database.Meals.consumed_at >= start, database.Meals.consumed_at < end).limit(1))
    if exists is None:
        return no_data_response(day)
    return calculate_progress(start, end, day, user_id, db)


def calculate_progress(start, end, day, user_id, db):
    totals_row = db.execute(
        select(*[
            func.coalesce(func.sum(case((getattr(database.Meals, key) >= 0, getattr(database.Meals, key)), else_=0)), 0).label(key)
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
            database.Goals.effective_date <= day,
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

    return {"date": day.isoformat(), "timezone": "UTC" if start.hour == 0 else "requested local day", "nutrients": progress}

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