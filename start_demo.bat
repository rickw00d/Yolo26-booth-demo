@echo off
rem YOLO26 booth demo launcher (Windows).
rem Keep this file pure ASCII with CRLF line endings: cmd.exe misreads
rem UTF-8 text or LF-only files and splits commands into fragments.
rem Set NO_BROWSER=1 to skip opening the browser automatically.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. See README.md - Quick start.
  pause
  exit /b 1
)
if not defined NO_BROWSER start "" /b cmd /c "timeout /t 8 >nul && start http://localhost:8000"
:loop
echo [%date% %time%] Starting YOLO26 demo...
".venv\Scripts\python.exe" run.py %*
echo [%date% %time%] Demo exited, restarting in 3 seconds (Ctrl+C to stop)...
timeout /t 3 /nobreak >nul
goto loop
