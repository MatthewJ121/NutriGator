# NutriGator

NutriGator is a full-stack nutrition tracking app built to help users set daily nutrition goals, log meals, and monitor progress toward their targets. The project combines a FastAPI backend with a React + Vite frontend so users can create accounts, manage goals, and quickly review how much of each nutrient they have consumed for the day. Premium users have access to AI recommendations based on their individual logs.

# Purpose

NutriGator is being developed as part of a course project. Some local development features are only readily accessible to colloborators in the course, and require the creation of your own database following the schema in /backend/database.py.

## Overview

The application currently supports:

- User registration and login
- Daily nutrition goal tracking for calories and key nutrients
- Meal logging with custom food entries and nutrient values
- Daily progress summaries comparing consumed totals against goals

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy, PostgreSQL/Neon
- Frontend: React, Vite, JavaScript
- Authentication: Better Auth via Neon Auth
- Testing: pytest for backend API coverage

## Project Structure

```text
NutriGator/
├── backend/
│   ├── migrations/
│   ├── routers/
│   ├── tests/
│   ├── backend.env.example
│   ├── database.py
│   ├── main.py
│   ├── requirements.txt
│   └── setup_neon.py
├── frontend/
│   ├── public/
│   ├── src/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
├── README.md
└── .gitignore
```

## Core Features

### Nutrition goals
Users can create and update nutrition goals for a specific date, including targets for:

- Calories
- Protein
- Carbs
- Cholesterol
- Trans fats
- Saturated fats
- Total fats

### Meal tracking
Meals are stored with:

- Food name
- Consumed timestamp
- Nutrient totals for the meal

### Progress reporting
The backend calculates daily totals and compares them against the most recent valid goal for the user. The frontend can display whether each nutrient is below, at, or above target.

### Account flow
Authentication requests are routed through Better Auth, and the backend creates a local profile record in the database for each authenticated user.

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm
- A PostgreSQL-compatible database or Neon project
Note that a private database is used for the purposes of the course this project is intended for.

### 1) Set up the Python backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python setup_neon.py
uvicorn main:app --reload
```

The API will run at:

- http://localhost:8000
- Swagger docs: http://localhost:8000/docs

### 2) Set up the frontend

Open a new terminal and run:

```bash
cd frontend
npm install
npm run dev
```

The frontend is served by Vite at:

- http://localhost:5173

## Useful API Endpoints

The backend currently exposes endpoints for auth, goals, meals, and progress, including:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `POST /api/goals`
- `PUT /api/goals`
- `GET /api/goals`
- `POST /meals`
- `GET /meals/today`
- `GET /progress/today`

## Testing

Backend tests are included in `backend/tests` and use FastAPI's test client with an in-memory SQLite database for isolated validation.

```bash
cd backend
pytest
```

Frontend validation can be checked with:

```bash
cd frontend
npm run build
```

## License

This project is currently intended for local development and coursework use unless a project-specific license is added later.