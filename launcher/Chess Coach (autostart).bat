@echo off
REM Auto-start helper: ensures the Chess Coach server is running, WITHOUT opening
REM a browser. Registered in the Startup folder so the server is always available.
setlocal
set "PROJ=C:\Users\jayce\chess-coach"
set "PYW=%PROJ%\.venv\Scripts\pythonw.exe"
set "PORT=8000"

if not exist "%PYW%" exit /b 0

REM Already running? do nothing.
powershell -NoProfile -Command "try{ Invoke-WebRequest 'http://127.0.0.1:%PORT%/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 exit /b 0

REM Start the windowless background server.
powershell -NoProfile -Command "$env:PORT='%PORT%'; Start-Process -FilePath '%PYW%' -ArgumentList @('-m','webapp.run_bg') -WorkingDirectory '%PROJ%' -WindowStyle Hidden"
exit /b 0
