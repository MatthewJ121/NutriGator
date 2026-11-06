"""Start the NutriGator API and connect its routers."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import externals, goals, profiles, meals

app = FastAPI(title="NutriGator Backend")

app.include_router(goals.router)
app.include_router(profiles.router)
app.include_router(externals.router)
app.include_router(meals.router)

# Allow our local React frontend to call FastAPI with session cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
