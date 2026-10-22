import os
import uuid
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Date, DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

load_dotenv(Path(__file__).resolve().parent / ".env.backend")
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_AUTH_URL = os.getenv("BASE_AUTH_URL")


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "Profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    first_name: Mapped[str] = mapped_column()
    is_premium: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)


# A value of -1 means the user has not picked a goal yet.
class Goals(Base):
    __tablename__ = "Goals"

    goal_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    calories: Mapped[float | None] = mapped_column(default=-1)
    protein: Mapped[float | None] = mapped_column(default=-1)
    carbs: Mapped[float | None] = mapped_column(default=-1)
    cholesterol: Mapped[float | None] = mapped_column(default=-1)
    trans_fats: Mapped[float | None] = mapped_column(default=-1)
    saturated_fats: Mapped[float | None] = mapped_column(default=-1)
    total_fats: Mapped[float | None] = mapped_column(default=-1)


class Meals(Base):
    __tablename__ = "Meals"

    meal_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    food_name: Mapped[str] = mapped_column()
    calories: Mapped[float] = mapped_column()
    protein: Mapped[float] = mapped_column()
    carbs: Mapped[float] = mapped_column()
    cholesterol: Mapped[float] = mapped_column()
    trans_fats: Mapped[float] = mapped_column()
    saturated_fats: Mapped[float] = mapped_column()
    total_fats: Mapped[float] = mapped_column()
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
