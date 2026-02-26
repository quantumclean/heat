@echo off
echo Starting HEAT Dashboard Server...
echo.
echo The dashboard will be available at:
echo    http://localhost:8080
echo.
echo Press Ctrl+C to stop the server
echo.
cd /d "%~dp0"
python -m http.server 8080


