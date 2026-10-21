import httpx
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from routers import goals

app = FastAPI()
app.include_router(goals.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import database
import uuid

# Testing database connections, use as reference for future database queries
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