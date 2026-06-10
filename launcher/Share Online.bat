@echo off
setlocal
title Chess Challenger - Public Link (keep open while sharing)
color 0F

REM Find cloudflared (PATH first, then the winget install location).
set "CF=cloudflared"
where cloudflared >nul 2>nul || set "CF=%LOCALAPPDATA%\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe"

REM Make sure the app server is running first.
powershell -NoProfile -Command "try{ Invoke-WebRequest 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if not %errorlevel%==0 (
  echo [!] The app is not running. Start it first with the "Chess Challenger" icon,
  echo     then run this again.
  echo.
  pause
  exit /b 1
)

echo ================================================================
echo            CHESS CHALLENGER  -  PUBLIC LINK
echo ================================================================
echo.
echo  Creating a public web address... this can take a few seconds.
echo  Look for a line like:  https://something.trycloudflare.com
echo  Send that link to anyone - it opens your app in their browser.
echo.
echo  * Keep THIS window open while you want the link to work.
echo  * Close this window to stop sharing.
echo ----------------------------------------------------------------
echo.

"%CF%" tunnel --url http://localhost:8000

echo.
echo Sharing stopped.
pause
