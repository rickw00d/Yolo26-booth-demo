@echo off
chcp 65001 >nul
cd /d "%~dp0"
:loop
echo [%date% %time%] 啟動 YOLO26 展示...
start "" /b cmd /c "timeout /t 6 >nul && start http://localhost:8000"
".venv\Scripts\python.exe" run.py
echo 程式結束,3 秒後自動重啟(按 Ctrl+C 停止)
timeout /t 3 >nul
goto loop
