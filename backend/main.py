from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine

engine = create_engine(DATABASE_URL, echo=True)
app = FastAPI()

#TODO file seperation
class profile(BaseModel):
    USERID: int
    first_name: str
    is_premium: bool
    is_active: bool
