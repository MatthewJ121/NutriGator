from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
import os
from dotenv import load_dotenv
from pathlib import Path

dir = Path(__file__).resolve().parent
load_dotenv(dir / ".env.backend")
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_AUTH_URL = os.getenv("BASE_AUTH_URL")

# Establish SQLAlchemy representations of database tables
class Base(DeclarativeBase):
    pass

class Profile(Base):
    __tablename__ = "Profiles"
    
    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, index=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column()
    is_premium: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

# NOTE: Negative values are used to indicate that the user has not set a goal for that specific metric.
class Goals(Base):
    __tablename__ = "Goals"
    
    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, index=True, autoincrement=False)
    calories: Mapped[float] = mapped_column()
    protein: Mapped[float] = mapped_column()
    carbs: Mapped[float] = mapped_column()
    cholesterol: Mapped[float] = mapped_column()
    trans_fats: Mapped[float] = mapped_column()
    saturated_fats: Mapped[float] = mapped_column()
    total_fats: Mapped[float] = mapped_column()

class Meals(Base):
    __tablename__ = "Meals"
    
    meal_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    food_name: Mapped[str] = mapped_column()
    calories: Mapped[float] = mapped_column()
    protein: Mapped[float] = mapped_column()
    carbs: Mapped[float] = mapped_column()
    cholesterol: Mapped[float] = mapped_column()
    trans_fats: Mapped[float] = mapped_column()
    saturated_fats: Mapped[float] = mapped_column()
    total_fats: Mapped[float] = mapped_column()