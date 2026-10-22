#TODO: add FastAPI routes for Gemini and FoodData APIs
"""
Handles all external API interactions.

URL Prefix:  
    /api

Endpoints:  
    TODO
"""

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