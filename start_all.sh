#!/usr/bin/env bash
set -e

echo "==================================================="
echo "Starting BrandGuard AI - Governance Portal (MVP)"
echo "==================================================="

if [ ! -f "backend/.env" ] && [ -f "backend/.env.example" ]; then
  cp "backend/.env.example" "backend/.env"
  echo "Created backend/.env from backend/.env.example"
fi

trap 'kill 0' SIGINT SIGTERM EXIT

echo "[1/2] Starting FastAPI Backend on http://localhost:8000 ..."
(
  cd backend
  if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
  fi
  uvicorn main:app --host 0.0.0.0 --port 8000
) &

echo "[2/2] Starting React (Vite) Frontend on http://localhost:5173 ..."
(
  cd frontend
  npm run dev
) &

wait
