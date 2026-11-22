@echo off
title HydroPower Intelligence - Engineering Suite
echo ====================================================================
echo             HYDROPOWER INTELLIGENCE - DESKTOP LAUNCHER
echo ====================================================================
echo.
echo [1/2] Verifying Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in system PATH.
    echo Please install Python 3.10+ from python.org and add it to PATH.
    pause
    exit /b 1
)

echo [2/2] Launching HydroPower Intelligence locally...
echo Starting Streamlit local desktop session at http://localhost:8501
echo.
streamlit run src\app.py --server.headless=false --server.port=8501 --browser.gatherUsageStats=false

if errorlevel 1 (
    echo.
    echo [ERROR] Application encountered an error during execution.
    pause
)
