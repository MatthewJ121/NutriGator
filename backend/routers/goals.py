"""
Handles all API requests related to goals.

URL Prefix:  
    /api/goals

Endpoints:  
    POST /{user_id} - Create a new goal for a specific user and date.  
    PUT /{user_id} - Update an existing goal for a specific user and date.  
    GET /{user_id} - Retrieve all goals associated with a user, sorted chronologically.  
    DELETE /{user_id}/{effective_date} - Delete a specified goal for a user.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field
import uuid
from datetime import date
import database

router = APIRouter(
    prefix="/api/goals",
    tags=["Goals"],
)

# Define request payload model
class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_date: date | None = Field(default_factory=date.today)
    calories: float = Field(default=-1, ge=0)
    protein: float = Field(default=-1, ge=0)
    carbs: float = Field(default=-1, ge=0)
    cholesterol: float = Field(default=-1, ge=0)
    trans_fats: float = Field(default=-1, ge=0)
    saturated_fats: float = Field(default=-1, ge=0)
    total_fats: float = Field(default=-1, ge=0)


'''API Endpoints'''

@router.post("/{target_user_id}", status_code=201)
async def create_goal(target_user_id: uuid.UUID, goal: Goal):
    """
    Create a new nutrition goal for a user.

    No request body is required. Only fields included in the request body will be
    considered tracked by the user. Note that a value of 0 does not untrack the field.
    Values of 0 indicate the user intends to intake no amount of that nutrient. 
    The effective date is today if unspecified.
    Do not use negative numbers to attempt to untrack a field.

    Parameters:  
        target_user_id (UUID): ID of user to create a goal for.  
        goal (Goal): Contains nutrient targets, goal id, and effective date.

    Returns:  
        dict: Confirmation message and the ID of the new goal.

    Raises:  
        HTTPException(404): The user profile does not exist.  
        HTTPException(409): An entry for the specified effective_date already exists.  
        HTTPException(500): There is a database write failure.
    """
    with Session(database.engine) as session:
        target = select(database.Profiles).where(database.Profiles.user_id == target_user_id)
        user = session.scalars(target).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        target = select(database.Goals).where(
            (database.Goals.user_id == target_user_id)
            & (database.Goals.effective_date == goal.effective_date))
        
        existing_goal = session.scalars(target).first()
        if existing_goal:
            raise HTTPException(status_code=409, detail="Goal for this date and user exists, use PUT instead")

        try:
            new_goal = database.Goals(
                user_id=target_user_id,
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


@router.put("/{target_user_id}")
async def update_goal(target_user_id: uuid.UUID, goal: Goal):
    """
    Update a user's existing goal at a specifed effective date.

    All request body fields are optional. Any unspecified values will be interpreted as 
    being untracked by the user. This means that any value in unspecified fields will
    be removed. This makes it simple to unselect specific fields, but means any data
    intended to remain unchanged must be retrieved and included in the request body.
    Do not use negative numbers to attempt to untrack a field.

    Note that a value of 0 does not untrack the field.
    Values of 0 indicate the user intends to intake no amount of that nutrient. 

    Args:  
        target_user_id: ID of user to modify a goal for.  
        goal (Goal): Contains nutrient targets, goal id, and effective date.
        
    Returns:  
        dict: Confirmation message and the ID of the new goal.

    Raises:  
        HTTPException(404): The user profile or goal do not exist.  
        HTTPException(500): There is a database write failure.
    """
    with Session(database.engine) as session:
        target = select(database.Profiles).where(database.Profiles.user_id == target_user_id)
        user = session.scalars(target).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        target = select(database.Goals).where(
            (database.Goals.user_id == target_user_id)
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


@router.get("/{target_user_id}")
async def get_goal(target_user_id: uuid.UUID):
    """
    Get all goals belonging to a user ordered by effective date.

    Untracked fields in a goal are denoted by -1 internally. When using retrieved
    field values, anything holding -1 should be discarded. 

    Args:  
        target_user_id: ID of the user whose goals are requested.
        
    Returns:  
        dict: Number of found goals and dict of those goals.

    Raises:  
        HTTPException(404): If the user profile does not exist.
    """
    with Session(database.engine) as session:
        target = select(database.Profiles).where(database.Profiles.user_id == target_user_id)
        user = session.scalars(target).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        target = (
            select(database.Goals)
            .where(database.Goals.user_id == target_user_id)
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


@router.delete("/{target_user_id}/{target_date}", status_code=204)
async def delete_goal(target_user_id: uuid.UUID, target_date: date):
    """
        Delete the goal for a user on the specified effective date.
        
        Args:  
            target_user_id: ID of the user for the goal.  
            target_date: Date on which a goal is to be deleted.
            
        Returns:  
            None.
    
        Raises:  
            HTTPException(404): The user profile or goal does not exist.  
            HTTPException(500): The database delete failed.
        """
    with Session(database.engine) as session:
        user_query = select(database.Profiles).where(
            database.Profiles.user_id == target_user_id
        )
        if not session.scalars(user_query).first():
            raise HTTPException(status_code=404, detail="User not found")

        goal_query = select(database.Goals).where(
            (database.Goals.user_id == target_user_id)
            & (database.Goals.effective_date == target_date)
        )
        goal = session.scalars(goal_query).first()
        if not goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        try:
            session.delete(goal)
            session.commit()
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail="Error deleting goal: " + str(e))

    return None