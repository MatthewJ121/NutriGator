"""
Handles all API requests related to profile creation and account authentication.

URL Prefix: 
    /api/profiles

Endpoints:
    POST /register or /new - Create a new user profile and account.  
    POST /login - Authenticate a user and create a session.
    POST /logout - Terminate a user's session.
    DELETE /delete - Remove a user profile and account.
"""
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.responses import JSONResponse

import database
from routers.auth_helpers import DB, UserId, auth_request, copy_session_cookie, local_user_id, upstream_cookies, clear_session_cookies, require_active_profile

auth_router = APIRouter(prefix="/api/profiles/auth", tags=["Authentication"])
password_router = APIRouter(prefix="/api/profiles/password", tags=["Password Management"])


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordUpdateRequest(BaseModel):
    current1: str = Field(min_length=7, max_length=128)
    current2: str = Field(min_length=7, max_length=128)
    new: str = Field(min_length=7, max_length=128)


'''Authenticaation Endpoints'''

@auth_router.post("/register", status_code=201)
@auth_router.post("/new", status_code=201, include_in_schema=False)
async def register(body: RegisterRequest, response: Response, request: Request, db: DB):
    """
    Create an authentication account and its local profile.

    Parameters:  
        body (RegisterRequest): Name, email, and password for the new account.  
        response (Response): Response used to set the session cookie.  
        request (Request): Request containing cookie and origin information.  
        db (DB): Database session used to create the local profile.

    Returns:  
        dict: Confirmation message and the new user's authentication details.

    Raises:  
        HTTPException(422): The name is blank or registration data is invalid.  
        HTTPException(4xx): The authentication service rejects the registration.  
        HTTPException(502): The authentication service is unavailable or returns no user ID.
    """
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

    copy_session_cookie(upstream, response, request)
    return {"message": "Account created", "user": {
        "id": str(auth_id), "email": str(body.email), "name": name,
    }}


@auth_router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response, db: DB):
    """
    Authenticate a user and create a session.

    Parameters:  
        body (LoginRequest): Email and password for the account.  
        request (Request): Request used to scope the session cookie.  
        response (Response): Response used to set the session cookie.

    Returns:  
        dict: The authenticated user and authentication token.

    Raises:  
        HTTPException(4xx): The authentication service rejects the credentials.  
        HTTPException(502): The authentication service is unavailable or returns invalid data.
    """
    upstream, data = await auth_request("POST", "sign-in/email", payload={
        "email": str(body.email), "password": body.password,
    })
    user = data.get("user") if isinstance(data, dict) else None
    auth_id = user.get("id") if isinstance(user, dict) else None

    if not auth_id:
        raise HTTPException(502, "Authentication service did not return a user ID")
    try:
        require_active_profile(local_user_id(str(auth_id)), db)
    except OperationalError as exc:
        raise HTTPException(
            503, "Profile database is unavailable; login could not be completed"
        ) from exc

    copy_session_cookie(upstream, response, request)
    return {"user": user, "token": data.get("token")}


@auth_router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Terminate the current session and clear its cookies.

    Parameters:
        request (Request): Request containing the current session cookies.
        response (Response): Response used to clear session cookies.

    Returns:
        dict: Logout confirmation when the authentication service succeeds.

    Raises:
        HTTPException: The authentication service error, after clearing local
            session cookies.
    """
    try:
        upstream, _ = await auth_request(
            "POST", "sign-out", payload={}, cookies=upstream_cookies(request.cookies),
        )
    except HTTPException as exc:
        failed_response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
        clear_session_cookies(request, failed_response)
        return failed_response

    copy_session_cookie(upstream, response, request)
    clear_session_cookies(request, response)
    return {"message": "Logged out"}


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1)


@auth_router.delete("/delete")
async def delete_account(body: DeleteAccountRequest, request: Request,
                         response: Response, user_id: UserId, db: DB):
    """Deactivate the signed-in user's profile after checking their password.

    Args:
        body: Password used to confirm the account belongs to this user.
        request: Current session cookies sent to Better Auth.
        response: Clears local session cookies after deactivation.
        user_id: User ID from the authenticated session.
        db: Database session for the profile update.

    Returns:
        dict: Confirmation that the account was deactivated.

    Raises:
        HTTPException(401): Session is missing or expired.
        HTTPException(403): Password is incorrect or account is inactive.
        HTTPException(500): Database update failed.
    """
    profile = db.get(database.Profiles, user_id)
    if profile is None:
        raise HTTPException(401, "Invalid user session")
    if not profile.is_active:
        raise HTTPException(403, "This account is not active")

    cookies = upstream_cookies(request.cookies)
    if not cookies:
        raise HTTPException(401, "Please log in first")

    # Check the password with Better Auth. We never store or compare it locally.
    try:
        _, verification = await auth_request(
            "POST", "verify-password",
            payload={"password": body.password}, cookies=cookies,
        )
    except HTTPException as exc:
        if exc.status_code == 401:
            raise HTTPException(403, "Incorrect password") from exc
        raise

    if isinstance(verification, dict) and any(
        verification.get(key) is False for key in ("status", "success", "valid")
    ):
        raise HTTPException(403, "Incorrect password")

    # Keep the profile and its meal history for possible account recovery.
    try:
        profile.is_active = False
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(500, "Unable to deactivate account") from exc

    # Deactivation still succeeds if Better Auth is temporarily unable to sign out.
    try:
        await auth_request("POST", "sign-out", payload={}, cookies=cookies)
    except HTTPException:
        pass
    clear_session_cookies(request, response)
    return {"message": "Account deactivated"}


'''Password Endpoints'''

@password_router.post("/forgot")
async def forgot_password(email: EmailStr, request: Request, response: Response):
    """
    Send the user a password reset link to their email if it exists using BetterAuth `requestResetRequest`.

    No error status will ever be returned if the email does not exist or fails to send. 

    Parameters:  
        email (str): Email included in request body to attempt to send a reset link to.

    Returns:  
        None.
"""
    raise HTTPException(501) # implemented in #56

@password_router.post("/reset")
async def reset_password(token: str, newPassword: str, request: Request, response: Response):
    """
    Update the user's password during a reset using BetterAuth `resetPassword`.

    Parameters:  
        token (str): Token included in the reset link.        
        newPassword (str): The new password to be reset to.

    Returns:  
        None.

    Raises:  
        HTTPException(401): Invalid session.
"""
    raise HTTPException(501) # implemented in #56


@password_router.post("/update")
async def update_password(body: PasswordUpdateRequest, request: Request, response: Response):
    """
    Update the password of a logged-in user.

    The user can update their password using their current password when logged-in. 

    Parameters:  
        current1 (str): Confirmation of existing password from field 1  
        current2 (str): Confirmation of existing password from field 2  
        new (str): New password to change to

    Returns:  
        None.

    Raises:  
        HTTPException(401): Invalid session  
        HTTPException(403): The current password is incorrect  
        HTTPException(422): The new password does not meet password requirements (#57)
"""
    raise HTTPException(501) # implemented in #56