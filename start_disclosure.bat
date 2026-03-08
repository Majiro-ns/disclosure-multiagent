@echo off
title disclosure-multiagent

echo ========================================
echo   disclosure-multiagent START
echo ========================================
echo.

REM 既存プロセスの停止 (port 8010 / port 3000)
echo [0/2] Stopping existing processes...
wsl bash -c "pkill -f 'uvicorn api.main' 2>/dev/null; pkill -f 'next dev' 2>/dev/null; sleep 1" >nul 2>&1

REM Backend (FastAPI port 8010)
echo [1/2] Starting backend...
start "disclosure-backend" wsl bash -c "cd /path/to/disclosure-multiagent && PYTHONPATH=scripts:. python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8010"

timeout /t 3 /nobreak >nul

REM Frontend (Next.js port 3000)
echo [2/2] Starting frontend...
start "disclosure-frontend" wsl bash -c "cd /path/to/disclosure-multiagent/web && npx next dev --turbopack --hostname 0.0.0.0 --port 3000"

timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo   Open in browser:
echo   http://localhost:3000
echo ========================================
echo.
pause
