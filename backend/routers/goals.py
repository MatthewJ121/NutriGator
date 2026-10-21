from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel
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
    calories: float | None = None
    protein: float | None = None
    carbs: float | None = None
    cholesterol: float | None = None
    trans_fats: float | None = None
    saturated_fats: float | None = None
    total_fats: float | None = None


'''API Endpoints'''

@router.post("/new_goal/{input_user_id}", status_code=201)
async def create_goal(input_user_id: uuid.UUID, goal: Goal):
    with Session(database.engine) as session:
        target = select(database.Profiles).where(database.Profiles.user_id == input_user_id)
        user = session.scalars(target).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        target = select(database.Goals).where((database.Goals.user_id == input_user_id) & (database.Goals.effective_date == goal.effective_date))
        existing_goal = session.scalars(target).first()
        if existing_goal:
            raise HTTPException(status_code=409, detail="Goal for this date and user exists, use /update_goal/ instead")

        try:
            new_goal = database.Goals(
                goal_id=None,
                user_id=input_user_id,
                effective_date=goal.effective_date,
                calories=goal.calories,
                protein=goal.protein,
                carbs=goal.carbs,
                cholesterol=goal.cholesterol,
                trans_fats=goal.trans_fats,
                saturated_fats=goal.saturated_fats,
                total_fats=goal.total_fats
            )
            session.add(new_goal)
            session.commit()
            session.refresh(new_goal)
            new_goal_id = new_goal.goal_id
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail="Error creating goal: " + str(e))

    return {"message": "Goal created successfully",
            "goal id": new_goal_id}