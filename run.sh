#!/bin/bash
cd "$(dirname "$0")"
echo "================================"
echo " VERITAS 3.0 — Full Stack Start"
echo "================================"
source venv/bin/activate
export PYTHONPATH=backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "Backend running with PID $BACKEND_PID"
cd frontend-react
npm install
npm run dev &
FRONTEND_PID=$!
echo "Frontend running with PID $FRONTEND_PID"
echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press CTRL+C to stop both servers"
wait
