@echo off
REM Bili UP Monitor - one-click start (double-click to run)
REM All logic lives in start.ps1; this wrapper only calls it with
REM -ExecutionPolicy Bypass so a Restricted policy cannot block it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 (
  echo.
  echo [START FAILED] See the error above.
  pause
)