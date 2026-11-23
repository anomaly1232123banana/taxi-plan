@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
python scan.py >> "logs\scheduler.log" 2>&1
if errorlevel 1 (
  rem retry once after 10 minutes (ping is a delay that works without a console)
  ping -n 601 127.0.0.1 >nul
  python scan.py >> "logs\scheduler.log" 2>&1
)
exit /b %errorlevel%
