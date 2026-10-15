import httpx
from fastapi import FastAPI
from sqlalchemy import engine, create_engine, select, text
from sqlalchemy.orm import Session

import database
import uuid

print("DATABASE_URL:", database.DATABASE_URL)
engine = create_engine(database.DATABASE_URL, echo=True)

# Testing database connections
'''
with Session(engine) as session:
    testProfile = database.Profile(user_id=uuid.uuid4(), first_name="John", is_premium=True)
    session.add(testProfile)

    testGoal = database.Goals(user_id=testProfile.user_id, calories=2000, protein=150)
    session.add(testGoal)
    session.commit()

    testUUID = testProfile.user_id
    print("Test UUID: ", testUUID)

    target = select(database.Profile).where(database.Profile.user_id == testUUID)
    user = session.scalars(target).first()
    target = select(database.Goals).where(database.Goals.user_id == testUUID)
    goal = session.scalars(target).first()

    if user:
        print(user.first_name)
        print(user.is_premium)
    if goal:
        print(goal.calories)
        '''