@echo off
title Cardiac AI Backend
echo ============================================
echo   CARDIAC AI BACKEND v2.0 — STARTUP
echo ============================================
echo.

cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Create venv if needed
if not exist "venv" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv venv
    echo [SETUP] Installing dependencies...
    call venv\Scripts\activate.bat
    pip install --upgrade pip -q
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM Create required directories
if not exist "models_saved" mkdir models_saved
if not exist "uploads\ecg" mkdir uploads\ecg
if not exist "data" mkdir data

REM Train model if not already done
if not exist "models_saved\risk_model.pkl" (
    echo.
    echo [TRAINING] Risk model not found. Training now...
    echo [TRAINING] This may take 2-5 minutes...
    echo.
    python train.py
    if errorlevel 1 (
        echo [ERROR] Training failed! Check internet connection.
        pause
        exit /b 1
    )
    echo.
) else (
    echo [OK] Model found: models_saved\risk_model.pkl
)

echo.
echo [STARTING] FastAPI server on http://localhost:8000
echo [DOCS]     http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
