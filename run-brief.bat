@echo off
REM AgentRadar weekly brief launcher for Windows.
REM Generates a trend+jobs+industry brief and emails it
REM (prints to this window instead if SMTP is not configured in .env).

cd /d "%~dp0"
echo.
echo Generating AgentRadar weekly brief (may take tens of seconds)...
echo.
".venv\Scripts\python.exe" -m agent_radar.brief
pause
