@echo off
REM AgentRadar Web UI launcher for Windows.
REM Starts the server; then open http://127.0.0.1:8000 in a browser.
REM Press Ctrl+C in this window to stop the server.

cd /d "%~dp0"
echo.
echo AgentRadar Web UI starting...
echo Open http://127.0.0.1:8000 in your browser. Press Ctrl+C here to stop.
echo.
".venv\Scripts\python.exe" -m agent_radar.web
pause
