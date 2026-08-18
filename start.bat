@echo off
title AI Inventory Assistant - Launcher

set "NODE_DIR=%USERPROFILE%\AppData\Local\nodejs\node-v24.19.0-win-x64"
set "PATH=%NODE_DIR%;%PATH%"

set "PROJECT_DIR=%~dp0"

echo [1/3] Starting backend (port 8000)...
start "AI-Backend" /D "%PROJECT_DIR%backend" cmd /k "py run.py"

echo [2/3] Starting frontend (port 5173)...
start "AI-Frontend" /D "%PROJECT_DIR%frontend" cmd /k "npm run dev"

echo [3/3] Waiting for services...
timeout /t 8 /nobreak >nul

start http://localhost:5173/

echo.
echo Done! Browser opened: http://localhost:5173/
echo To stop: close the two service windows.
echo.
pause
