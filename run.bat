@echo off
REM AgentRadar one-click launcher for Windows.
REM Double-click this file to start the CLI. No need to activate the venv manually.

cd /d "%~dp0"
".venv\Scripts\python.exe" -m agent_radar.cli
pause
