@echo off
setlocal
title Chess Coach Studio  (server - keep this window open)
chcp 65001 >nul
color 0F

set "PROJ=C:\Users\jayce\chess-coach"
set "PY=%PROJ%\.venv\Scripts\python.exe"
set "PORT=8000"
set "URL=http://127.0.0.1:%PORT%"

cd /d "%PROJ%"

if not exist "%PY%" (
  echo [ERROR] Python venv not found: %PY%
  echo Re-create it:  python -m venv .venv ^&^& pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo ================================================
echo            CHESS COACH STUDIO
echo   Record / upload a game  -^>  AI evaluation
echo   then review it on a visual board.
echo ================================================
echo.
echo Server starting at %URL%
echo Your browser will open automatically in a few seconds.
echo.
echo *** Keep this window open while you use the app. ***
echo *** Close this window to stop the server.        ***
echo.

REM open the browser a few seconds after the server has had time to start
start "" cmd /c "timeout /t 3 >nul ^& start "" %URL%"

"%PY%" -m uvicorn webapp.server:app --host 127.0.0.1 --port %PORT%

echo.
echo Server stopped.
pause
