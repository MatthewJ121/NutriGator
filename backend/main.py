import httpx
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from routers import goals, profiles, externals

app = FastAPI()
app.include_router(goals.router)
app.include_router(profiles.router)
app.include_router(externals.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"
                   "http://localhost:3000"
                   "https://MatthewJ121.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)