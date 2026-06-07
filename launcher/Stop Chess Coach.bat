@echo off
title Stop Chess Coach
REM Stop the background Chess Coach server (the venv python running uvicorn).
powershell -NoProfile -Command "Get-Process python,pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*chess-coach*venv*' } | Stop-Process -Force"
echo Chess Coach server has been stopped.
timeout /t 2 >nul
