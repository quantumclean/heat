@echo off
REM ===================================================================
REM HEAT — Start WebSocket Real-Time Server
REM
REM Runs the HEAT WebSocket push server on localhost:8765.
REM Clients connect via websocket-client.js in the frontend.
REM
REM Usage:
REM   start-websocket.bat              (uses default venv)
REM   start-websocket.bat 8765         (custom port)
REM ===================================================================

set PORT=%1
if "%PORT%"=="" set PORT=8765

echo ============================================
echo HEAT WebSocket Server
echo Port: %PORT%
echo ============================================
echo.

REM Activate virtual environment
if exist "C:\Programming\heat\.venv\Scripts\activate.bat" (
    call "C:\Programming\heat\.venv\Scripts\activate.bat"
) else if exist "C:\Programming\.venv\Scripts\activate.bat" (
    call "C:\Programming\.venv\Scripts\activate.bat"
)

cd /d "%~dp0processing"

echo Starting WebSocket server on ws://localhost:%PORT% ...
echo Press Ctrl+C to stop.
echo.

python -c "import asyncio; from websocket_server import start_server; asyncio.run(start_server('0.0.0.0', %PORT%))"

pause
