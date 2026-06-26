@echo off
title ASA-Studio
cd /d "%~dp0"

echo.
echo === ASA-Studio ===
echo.
echo Starting...
pip install -r requirements.txt -q 2>nul
start http://localhost:8000
uvicorn server:app --host 0.0.0.0 --port 8000
pause
