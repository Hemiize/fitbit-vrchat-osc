@echo off
rem Fitbit-Air-Puls -> VRChat OSC, unsichtbar mit Tray-Symbol. Log: fitbit-osc.log. Beenden über das Tray-Menü.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0hr_osc.py" --tray %*
