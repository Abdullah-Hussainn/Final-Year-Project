@echo off
REM Start the FastAPI backend server
cd /d "%~dp0"
uvicorn main:app --reload --host 0.0.0.0 --port 8000

