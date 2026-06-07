@echo off
setlocal
title Chess Coach launcher
set "PROJ=C:\Users\jayce\chess-coach"
set "PYW=%PROJ%\.venv\Scripts\pythonw.exe"
set "PORT=8000"
set "URL=http://127.0.0.1:%PORT%/"

if not exist "%PYW%" (
  echo [ERROR] pythonw not found: %PYW%
  echo Recreate the venv:  python -m venv .venv  then  pip install -r requirements.txt
  pause
  exit /b 1
)

REM 1) Already running? Just open the browser and quit.
powershell -NoProfile -Command "try{ Invoke-WebRequest '%URL%api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  start "" "%URL%"
  exit /b 0
)

REM 2) Start the server WINDOWLESS and detached, so it keeps running after this
REM    launcher closes. There is no server window to accidentally close.
REM    run_bg redirects logs to a file so pythonw has no console to crash on.
powershell -NoProfile -Command "$env:PORT='%PORT%'; Start-Process -FilePath '%PYW%' -ArgumentList @('-m','webapp.run_bg') -WorkingDirectory '%PROJ%' -WindowStyle Hidden"

REM 3) Wait until it is ready, then open the browser.
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ Start-Sleep -Milliseconds 500; try{ Invoke-WebRequest '%URL%api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; $ok=$true; break } catch {} }; if($ok){exit 0}else{exit 1}"
if %errorlevel%==0 (
  start "" "%URL%"
  exit /b 0
)

echo.
echo [ERROR] The server did not start. Run the debug launcher to see the error:
echo   launcher\Chess Coach Studio (debug).bat
echo.
pause
