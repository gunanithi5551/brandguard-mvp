@echo off
echo ===================================================
echo Starting BrandGuard AI - Governance Portal (MVP)
echo ===================================================

if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy "backend\.env.example" "backend\.env" >nul
        echo Created backend\.env from backend\.env.example
    )
)

echo [1/2] Booting FastAPI + CrewAI + ChromaDB Backend on http://localhost:8000 ...
start "BrandGuard Backend" cmd /k "cd backend && (if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat) && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/2] Booting React (Vite) Frontend on http://localhost:5173 ...
start "BrandGuard Frontend" cmd /k "cd frontend && npm run dev"

echo Both servers are launching in separate terminal windows.
echo Backend API Docs: http://localhost:8000/docs
echo Frontend Portal:  http://localhost:5173
