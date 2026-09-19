@echo off
REM Bili UP Monitor - stop the backend (double-click to run)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" %*
if errorlevel 1 pause