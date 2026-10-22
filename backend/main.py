"""Account registration, daily meals, and goal progress for NutriGator."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import database

app = FastAPI(title="NutriGator Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

NUTRIENTS = (
    "calories", "protein", "carbs", "cholesterol", "trans_fats",
    "saturated_fats", "total_fats",
)

# Don't connect to Neon until the first request needs the database.
engine = create_engine(database.DATABASE_URL, pool_pre_ping=True) if database.DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine) if engine else None


def get_db():
    if SessionLocal is None:
        raise HTTPException(503, "DATABASE_URL is not configured")
    with SessionLocal() as session:
        yield session


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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


def auth_url(route: str):
    # BASE_AUTH_URL should include /api/auth if that is where Better Auth lives.
    if not database.BASE_AUTH_URL:
        raise HTTPException(503, "BASE_AUTH_URL is not configured")
    return f"{database.BASE_AUTH_URL.rstrip('/')}/{route}"


async def auth_request(method: str, route: str, *, payload=None, cookies=None):
    # Neon checks the origin for email sign-up and login requests.
    headers = {"Origin": "http://localhost:5173"}
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            result = await client.request(
                method, auth_url(route), json=payload, cookies=cookies, headers=headers
            )
    except httpx.RequestError as exc:
        raise HTTPException(502, "Authentication service is unavailable") from exc
    try:
        data = result.json()
    except ValueError:
        raise HTTPException(502, "Authentication service returned invalid data")
    if result.status_code >= 400:
        # Don't send internal provider errors or sensitive details to the browser.
        if result.status_code in (400, 401, 403, 409, 422):
            raise HTTPException(result.status_code, data.get("message", "Authentication failed") if isinstance(data, dict) else "Authentication failed")
        raise HTTPException(502, "Authentication service returned an error")
    return result, data


def local_user_id(auth_id: str) -> uuid.UUID:
    # Better Auth may use text IDs, while our existing SQL tables use UUIDs.
    # This keeps one repeatable UUID per Better Auth account without changing its tables.
    return uuid.uuid5(uuid.NAMESPACE_URL, f"nutrigator:better-auth:{auth_id}")


def copy_session_cookie(upstream: httpx.Response, response: Response):
    # Better Auth owns the cookie. We only forward it to the browser.
    # The production deployment should use a shared trusted domain and HTTPS.
    for value in upstream.headers.get_list("set-cookie"):
        response.headers.append("set-cookie", value)


@app.post("/auth/register", status_code=201)
async def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Name cannot be blank")
    upstream, data = await auth_request("POST", "sign-up/email", payload={
        "name": name, "email": str(body.email), "password": body.password
    })
    user = data.get("user") or {}
    auth_id = user.get("id")
    if not auth_id:
        raise HTTPException(502, "Authentication service did not return a user ID")

    user_id = local_user_id(str(auth_id))
    if not db.get(database.Profile, user_id):
        db.add(database.Profile(user_id=user_id, first_name=name.split()[0], is_premium=False, is_active=True))
        db.commit()
    copy_session_cookie(upstream, response)
    return {"message": "Account created", "user": {"id": str(auth_id), "email": str(body.email), "name": name}}


@app.post("/auth/login")
async def login(body: LoginRequest, response: Response):
    upstream, data = await auth_request("POST", "sign-in/email", payload={
        "email": str(body.email), "password": body.password
    })
    copy_session_cookie(upstream, response)
    return {"user": data.get("user"), "token": data.get("token")}


async def current_user(request: Request):
    # Never take a user ID from the meal request. Check the actual session instead.
    _, data = await auth_request("GET", "get-session", cookies=request.cookies)
    user = data.get("user") if isinstance(data, dict) else None
    if not user or not user.get("id"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in first")
    return local_user_id(str(user["id"]))


UserId = Annotated[uuid.UUID, Depends(current_user)]
DB = Annotated[Session, Depends(get_db)]


def meal_data(meal: database.Meals):
    return {"meal_id": meal.meal_id, "food_name": meal.food_name,
            "consumed_at": meal.consumed_at.isoformat(),
            **{field: getattr(meal, field) for field in NUTRIENTS}}


@app.post("/meals", status_code=201)
def add_meal(body: MealRequest, user_id: UserId, db: DB):
    profile = db.get(database.Profile, user_id)
    if not profile or not profile.is_active:
        raise HTTPException(403, "This account is not active")
    meal = database.Meals(user_id=user_id, food_name=body.food_name.strip(),
                          **{field: getattr(body, field) for field in NUTRIENTS})
    if not meal.food_name:
        raise HTTPException(422, "Food name cannot be blank")
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return meal_data(meal)


@app.get("/meals/today")
def todays_meals(user_id: UserId, db: DB):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    meals = db.scalars(select(database.Meals).where(
        database.Meals.user_id == user_id,
        database.Meals.consumed_at >= today,
        database.Meals.consumed_at < today + timedelta(days=1)
    ).order_by(database.Meals.consumed_at)).all()
    return [meal_data(meal) for meal in meals]


@app.get("/progress/today")
def today_progress(user_id: UserId, db: DB):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    totals_row = db.execute(select(*[
        func.coalesce(func.sum(getattr(database.Meals, key)), 0).label(key)
        for key in NUTRIENTS
    ]).where(database.Meals.user_id == user_id,
            database.Meals.consumed_at >= today,
            database.Meals.consumed_at < today + timedelta(days=1))).one()
    # Find the latest goal that was active by today.
    goals = db.scalars(
        select(database.Goals)
        .where(
            database.Goals.user_id == user_id,
            database.Goals.effective_date <= today.date()
        )
        .order_by(database.Goals.effective_date.desc(), database.Goals.goal_id.desc())
        .limit(1)
    ).first()
    totals = dict(zip(NUTRIENTS, totals_row))
    progress = {}
    for key in NUTRIENTS:
        target = getattr(goals, key) if goals else -1
        consumed = float(totals[key])
        if target is None or target < 0:
            progress[key] = {"consumed": consumed, "goal": None, "percentage": None,
                             "status": "not_set", "met": False}
        else:
            percentage = round(consumed / target * 100, 1) if target > 0 else (100.0 if consumed == 0 else None)
            progress[key] = {"consumed": consumed, "goal": target,
                             "percentage": percentage, "status": "below" if consumed < target else ("at" if consumed == target else "above"),
                             "met": consumed >= target}
    return {"date": today.date().isoformat(), "timezone": "UTC", "nutrients": progress}
