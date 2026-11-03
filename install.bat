@echo off
rem Richtet die Python-Umgebung ein (einmalig). Braucht Python 3.11+ von python.org, "py"-Launcher inklusive.
cd /d "%~dp0"
where py >nul 2>nul || (echo Python nicht gefunden - bitte von https://www.python.org/downloads/ installieren & pause & exit /b 1)
if not exist .venv py -3 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo Fertig. Start: start.bat (mit Fenster) oder start-tray.bat (unsichtbar, Tray-Symbol)
echo Autostart mit SteamVR: .venv\Scripts\python.exe register_steamvr.py
pause
