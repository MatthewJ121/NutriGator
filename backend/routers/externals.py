#TODO: add FastAPI routes for Gemini and FoodData APIs
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid
from datetime import date
import database

router = APIRouter(
    prefix="/api",
    tags=["Externals"],
)