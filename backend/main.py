"""Start the NutriGator API and connect its routers."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import externals, goals, profiles, meals

app = FastAPI(title="NutriGator Backend")
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "https://matthewj121.github.io",
    ).split(",")
    if origin.strip()
]

app.include_router(goals.router)
app.include_router(profiles.auth_router)
app.include_router(profiles.password_router)
app.include_router(profiles.premium_router)
app.include_router(externals.router)
app.include_router(meals.router)
app.include_router(meals.progress_router)
app.include_router(meals.legacy_router)

# Allow our local React frontend to call FastAPI with session cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Detail"],
)
