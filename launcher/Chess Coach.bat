@echo off
setlocal
title Chess Coach - Game Analysis
chcp 65001 >nul
color 0F

set "PROJ=C:\Users\jayce\chess-coach"
set "PY=%PROJ%\.venv\Scripts\python.exe"

cd /d "%PROJ%"

if not exist "%PY%" (
  echo [ERROR] Python venv not found: %PY%
  echo Re-create it:  python -m venv .venv ^&^& pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo ============================================
echo            CHESS COACH  -  M1
echo   Engine-accurate per-move game analysis
echo ============================================
echo.

if not "%~1"=="" (
  set "PGN=%~1"
) else (
  set "PGN="
  set /p "PGN=Drag a .pgn onto this window, or type a path (Enter = sample game): "
)

if "%PGN%"=="" set "PGN=%PROJ%\data\sample.pgn"
set PGN=%PGN:"=%

if not exist "%PGN%" (
  echo.
  echo [ERROR] File not found: %PGN%
  echo.
  pause
  exit /b 1
)

echo.
echo Analyzing: %PGN%
echo Engine: Stockfish depth 18  ^(this can take a few seconds^)
echo --------------------------------------------
echo.
"%PY%" -m chess_coach.cli "%PGN%" --depth 18

echo.
echo --------------------------------------------
echo Done. Tip: drag any .pgn file onto this icon to analyze it.
echo.
pause
