@echo off
rem Fitbit-Air-Puls -> VRChat OSC (Port 9000). Weitere Optionen: --chatbox, --max 200, --demo
cd /d "%~dp0"
".venv\Scripts\python.exe" hr_osc.py %*
pause
