"""Shared authentication helpers for NutriGator."""
import os
import uuid
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

import database


def get_db():
    if not database.DATABASE_URL:
        raise HTTPException(503, "DATABASE_URL is not configured")
    with Session(database.engine) as session:
        yield session


DB = Annotated[Session, Depends(get_db)]


def local_user_id(auth_id: str) -> uuid.UUID:
    # Keep the same UUID for each Better Auth account.
    return uuid.uuid5(uuid.NAMESPACE_URL, f"nutrigator:better-auth:{auth_id}")


async def auth_request(method: str, route: str, *, payload=None, cookies=None):
    if not database.BASE_AUTH_URL:
        raise HTTPException(503, "BASE_AUTH_URL is not configured")

    # Neon checks the app origin on sign-up and login requests.
    origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    url = f"{database.BASE_AUTH_URL.rstrip('/')}/{route}"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            result = await client.request(
                method, url, json=payload, cookies=cookies, headers={"Origin": origin}
            )
    except httpx.RequestError as exc:
        raise HTTPException(502, "Authentication service is unavailable") from exc

    try:
        data = result.json()
    except ValueError as exc:
        raise HTTPException(502, "Authentication service returned invalid data") from exc

    if result.status_code >= 400:
        if result.status_code in (400, 401, 403, 409, 422):
            message = data.get("message", "Authentication failed") if isinstance(data, dict) else "Authentication failed"
            raise HTTPException(result.status_code, message)
        raise HTTPException(
            502,
            f"Authentication service returned HTTP {result.status_code} for {route}",
        )
    return result, data


def copy_session_cookie(upstream: httpx.Response, response: Response):
    # Forward the cookie from Better Auth, without creating our own token.
    for cookie in upstream.headers.get_list("set-cookie"):
        response.headers.append("set-cookie", cookie)


async def current_user(request: Request) -> uuid.UUID:
    # Never take the user ID from the meal request itself.
    if not request.cookies:
        raise HTTPException(401, "Please log in first")
    _, data = await auth_request("GET", "get-session", cookies=request.cookies)
    user = data.get("user") if isinstance(data, dict) else None
    if not user or not user.get("id"):
        raise HTTPException(401, "Please log in first")
    return local_user_id(str(user["id"]))


UserId = Annotated[uuid.UUID, Depends(current_user)]
