@echo off
title Sync Tool Web Server
echo Starting Sync Tool Web Application Server on 0.0.0.0:8000...
cd /d "%~dp0"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
