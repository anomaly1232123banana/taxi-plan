@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
python scan.py >> "logs\scheduler.log" 2>&1
