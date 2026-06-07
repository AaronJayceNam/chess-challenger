@echo off
setlocal
title Chess Coach (debug - shows server logs)
set "PROJ=C:\Users\jayce\chess-coach"
set "PY=%PROJ%\.venv\Scripts\python.exe"
set "PORT=8000"
set "CC_OPEN_BROWSER=1"
cd /d "%PROJ%"
echo Running the server with visible logs. Close this window to stop it.
echo Open http://127.0.0.1:%PORT% if the browser does not open.
echo ----------------------------------------------------------------
"%PY%" -m uvicorn webapp.server:app --host 127.0.0.1 --port %PORT%
echo.
echo Server stopped.
pause
