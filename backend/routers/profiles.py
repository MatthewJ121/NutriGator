"""
Handles all API requests related to profile management.

URL Prefix:  
    /api/profile

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
    prefix="/api/profile",
    tags=["Profile"],
)

'''Request payload models'''

class NewProfile(BaseModel):
    #NOTE: account info related to BetterAuth and User table 
    user_id: uuid.UUID
    first_name: str
    is_active: bool | None = True
    is_premium: bool | None = False

class LoginInfo(BaseModel):
    pass

class LogoutInfo(BaseModel):
    pass

class PasswordForgot(BaseModel):
    pass

class PasswordUpdate(BaseModel):
    pass


'''API Endpoints'''

@router.post("/new", status_code=201)
async def create_profile(new_profile: NewProfile):
    raise HTTPException(status_code=501)

@router.post("/sign-in")
async def sign_in(info: LoginInfo):
    raise HTTPException(status_code=501)

@router.post("/sign-out")
async def sign_out(info: LogoutInfo):
    raise HTTPException(status_code=501)

@router.post("/password/forgot")
async def forgot_password(info: PasswordForgot):
    raise HTTPException(status_code=501)

@router.post("/password/update")
async def update_password(info: PasswordUpdate):
    raise HTTPException(status_code=501)