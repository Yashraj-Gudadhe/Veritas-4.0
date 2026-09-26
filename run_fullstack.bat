@echo off
title VERITAS 2.0 — Full Stack (Backend + React Frontend)
color 0B

echo ==========================================================================
echo       VERITAS 2.0 — Evidence-Aware Medical Decision Intelligence
echo       React Chat Interface + FastAPI Backend
echo ==========================================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and try again.
    pause & exit /b 1
)

:: Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install Node.js 18+ and try again.
    pause & exit /b 1
)

echo [1/2] Starting VERITAS FastAPI Backend on http://localhost:8000 ...
start "VERITAS Backend" cmd /c "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Starting React Frontend on http://localhost:5173 ...
echo       (Waiting 5 seconds for backend to start...)
timeout /t 5 /nobreak >nul

:: Open browser after a short delay
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5173"

cd frontend-react
npm run dev

pause
