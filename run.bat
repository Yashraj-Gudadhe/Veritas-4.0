@echo off
title VERITAS — Evidence-Aware Decision Intelligence
color 0B

echo =========================================================================
echo          VERITAS — Evidence-Aware Medical Decision Intelligence
echo =========================================================================
echo.
echo [1/3] Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b 1
)

echo [2/3] Starting VERITAS FastAPI Server on http://localhost:8000 ...
echo       Press CTRL+C at any time to stop the server.
echo.

:: Open default web browser after a short delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: Launch Uvicorn server on localhost:8000
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

if errorlevel 1 (
    echo.
    echo [ERROR] Server encountered an issue while running.
    pause
)
