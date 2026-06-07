@echo off
setlocal
title Chess Coach Studio  (server - keep this window open)
color 0F

set "PROJ=C:\Users\jayce\chess-coach"
set "PY=%PROJ%\.venv\Scripts\python.exe"
set "PORT=8000"
set "CC_OPEN_BROWSER=1"

cd /d "%PROJ%"

if not exist "%PY%" (
  echo [ERROR] Python venv not found: %PY%
  echo Recreate it:  python -m venv .venv   then   pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo ================================================
echo               CHESS COACH STUDIO
echo ================================================
echo.
echo  The chess app will open in your browser shortly.
echo  If it does not open, go to:  http://127.0.0.1:%PORT%
echo.
echo  * This black window is the server. Keep it open while using the app.
echo  * To quit, just close this window.
echo.
echo ------------------------------------------------

"%PY%" -m uvicorn webapp.server:app --host 127.0.0.1 --port %PORT%

echo.
echo Server stopped.
pause
