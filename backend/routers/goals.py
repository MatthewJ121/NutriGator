from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import uuid
from datetime import date
import database

router = APIRouter(
    prefix="/api/goals",
    tags=["Goals"],
)

# Define request body model
class Goal(BaseModel):
    effective_date: date | None = date.today()
    calories: float = Field(default=None, ge=0)
    protein: float = Field(default=None, ge=0)
    carbs: float = Field(default=None, ge=0)
    cholesterol: float = Field(default=None, ge=0)
    trans_fats: float = Field(default=None, ge=0)
    saturated_fats: float = Field(default=None, ge=0)
    total_fats: float = Field(default=None, ge=0)


'''API Endpoints'''

@router.post("/{input_user_id}", status_code=201)
async def create_goal(input_user_id: uuid.UUID, goal: Goal):
    with Session(database.engine) as session:
        target = select(database.Profiles).where(database.Profiles.user_id == input_user_id)
        user = session.scalars(target).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        target = select(database.Goals).where(
            (database.Goals.user_id == input_user_id)
            & (database.Goals.effective_date == goal.effective_date))
        
        existing_goal = session.scalars(target).first()
        if existing_goal:
            raise HTTPException(status_code=409, detail="Goal for this date and user exists, use PUT instead")

        try:
            new_goal = database.Goals(
                goal_id=None,
                user_id=input_user_id,
                effective_date=goal.effective_date,
                calories=goal.calories,
                protein=round(goal.protein, 1),
                carbs=round(goal.carbs, 1),
                cholesterol=round(goal.cholesterol, 1),
                trans_fats=round(goal.trans_fats, 1),
                saturated_fats=round(goal.saturated_fats, 1),
                total_fats=round(goal.total_fats, 1)
            )
            session.add(new_goal)
            session.commit()
            session.refresh(new_goal)
            goal_id = new_goal.goal_id
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail="Error creating goal: " + str(e))

    return {"message": "Goal created successfully",
            "goal id": goal_id}

@router.put("/{input_user_id}")
async def update_goal(input_user_id: uuid.UUID, goal: Goal):
    with Session(database.engine) as session:
        target = select(database.Profiles).where(database.Profiles.user_id == input_user_id)
        user = session.scalars(target).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        target = select(database.Goals).where(
            (database.Goals.user_id == input_user_id)
            & (database.Goals.effective_date == goal.effective_date)
        )
        existing_goal = session.scalars(target).first()
        if not existing_goal:
            raise HTTPException(status_code=404, detail="Goal not found, did you mean to use post?")

        try:
            existing_goal.calories = round(goal.calories, 1)
            existing_goal.protein = round(goal.protein, 1)
            existing_goal.carbs = round(goal.carbs, 1)
            existing_goal.cholesterol = round(goal.cholesterol, 1)
            existing_goal.trans_fats = round(goal.trans_fats, 1)
            existing_goal.saturated_fats = round(goal.saturated_fats, 1)
            existing_goal.total_fats = round(goal.total_fats, 1)
            session.commit()
            goal_id = existing_goal.goal_id
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail="Error updating goal: " + str(e))

    return {"message": "Goal updated successfully", 
            "goal id": goal_id}

@router.get("/{input_user_id}")
async def get_goal(input_user_id: uuid.UUID):
    with Session(database.engine) as session:
        target = select(database.Profiles).where(database.Profiles.user_id == input_user_id)
        user = session.scalars(target).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        target = (
            select(database.Goals)
            .where(database.Goals.user_id == input_user_id)
            .order_by(database.Goals.effective_date)
        )
        goals = session.scalars(target).all()
        num_goals = len(goals)

    return {
        "message": f"Found {num_goals} goals for this user.",
        "goals": [
            {
                "goal_id": goal.goal_id,
                "user_id": goal.user_id,
                "effective_date": goal.effective_date,
                "calories": goal.calories,
                "protein": goal.protein,
                "carbs": goal.carbs,
                "cholesterol": goal.cholesterol,
                "trans_fats": goal.trans_fats,
                "saturated_fats": goal.saturated_fats,
                "total_fats": goal.total_fats,
            }
            for goal in goals
        ],
    }
