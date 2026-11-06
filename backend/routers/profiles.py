"""Profile creation and account authentication routes."""
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from starlette.responses import JSONResponse

import database
from routers.auth_helpers import DB, auth_request, copy_session_cookie, local_user_id

router = APIRouter(tags=["Profiles"])


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/auth/register", status_code=201)
@router.post("/api/profile/new", status_code=201, include_in_schema=False)
async def register(body: RegisterRequest, response: Response, db: DB):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Name cannot be blank")

    # Better Auth creates the account and handles the password.
    upstream, data = await auth_request("POST", "sign-up/email", payload={
        "name": name, "email": str(body.email), "password": body.password,
    })
    user = data.get("user") or {}
    auth_id = user.get("id")
    if not auth_id:
        raise HTTPException(502, "Authentication service did not return a user ID")

    user_id = local_user_id(str(auth_id))
    if not db.get(database.Profiles, user_id):
        db.add(database.Profiles(
            user_id=user_id, first_name=name.split()[0],
            is_premium=False, is_active=True,
        ))
        db.commit()

    copy_session_cookie(upstream, response)
    return {"message": "Account created", "user": {
        "id": str(auth_id), "email": str(body.email), "name": name,
    }}


@router.post("/auth/login")
async def login(body: LoginRequest, response: Response):
    upstream, data = await auth_request("POST", "sign-in/email", payload={
        "email": str(body.email), "password": body.password,
    })
    copy_session_cookie(upstream, response)
    return {"user": data.get("user"), "token": data.get("token")}


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    try:
        upstream, _ = await auth_request(
            "POST", "sign-out", payload={}, cookies=request.cookies,
        )
    except HTTPException as exc:
        failed_response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
        for cookie_name in request.cookies:
            if cookie_name.endswith("better-auth.session_token"):
                failed_response.delete_cookie(
                    cookie_name,
                    path="/",
                    secure=cookie_name.startswith("__Secure-"),
                    httponly=True,
                    samesite="lax",
                )
        return failed_response

    copy_session_cookie(upstream, response)
    return {"message": "Logged out"}


# Other profile operations are still handled by Matthew's assigned work.
