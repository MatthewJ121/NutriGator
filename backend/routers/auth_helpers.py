"""Shared authentication helpers for NutriGator."""
import os
import base64
import re
from http.cookies import SimpleCookie
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


LOCAL_AUTH_COOKIE_PREFIX = "nutrigator_auth_"


def local_cookie_name(upstream_name):
    encoded = base64.urlsafe_b64encode(upstream_name.encode()).decode().rstrip("=")
    return LOCAL_AUTH_COOKIE_PREFIX + encoded


def upstream_cookies(cookies):
    """Restore upstream cookie names; their signed values are never modified."""
    restored = {}
    for name, value in cookies.items():
        if name.startswith(LOCAL_AUTH_COOKIE_PREFIX):
            encoded = name[len(LOCAL_AUTH_COOKIE_PREFIX):]
            try:
                original = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True).decode()
            except (ValueError, UnicodeError):
                continue
            if re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", original):
                restored[original] = value
        elif ("auth" in name and ("session" in name or "token" in name)) or name in {"session_token", "session_data", "session_challenge", "session_challange"}:
            restored[name] = value
    return restored


def copy_session_cookie(upstream: httpx.Response, response: Response, request: Request):
    """Scope Neon cookies to this API's host and path for same-site proxying.

    Only HTTP loopback development uses unprefixed, non-Secure local names.
    HTTPS retains Secure; all cookies remain HttpOnly and SameSite=Lax.
    Neon still validates the original signed cookie on every protected request.
    """
    local_http = request.url.scheme == "http" and request.url.hostname in {"localhost", "127.0.0.1", "::1", "testserver"}
    for header in upstream.headers.get_list("set-cookie"):
        # Partitioned is unsupported by Python 3.12's cookie parser and is
        # unnecessary when the auth cookie belongs to our same-site API.
        parsed = SimpleCookie()
        parsed.load(re.sub(r";\s*Partitioned(?=;|$)", "", header, flags=re.IGNORECASE))
        for name, cookie in parsed.items():
            response.set_cookie(
                key=local_cookie_name(name) if local_http else name,
                value=cookie.value,
                max_age=int(cookie["max-age"]) if cookie["max-age"] else None,
                expires=cookie["expires"] or None,
                path="/",
                secure=not local_http,
                httponly=True,
                samesite="lax",
            )


def clear_session_cookies(request: Request, response: Response):
    for name in request.cookies:
        if name.startswith(LOCAL_AUTH_COOKIE_PREFIX) or ("auth" in name and "session" in name) or name in {"session_token", "session_data", "session_challenge", "session_challange"}:
            response.delete_cookie(name, path="/", secure=request.url.scheme == "https", httponly=True, samesite="lax")


async def current_user(request: Request) -> uuid.UUID:
    # Never take the user ID from the meal request itself.
    cookies = upstream_cookies(request.cookies)
    if not cookies:
        raise HTTPException(401, "Please log in first")
    _, data = await auth_request("GET", "get-session", cookies=cookies)
    user = data.get("user") if isinstance(data, dict) else None
    if not user or not user.get("id"):
        raise HTTPException(401, "Please log in first")
    return local_user_id(str(user["id"]))


UserId = Annotated[uuid.UUID, Depends(current_user)]
