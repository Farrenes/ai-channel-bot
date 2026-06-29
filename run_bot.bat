@echo off
setlocal enabledelayedexpansion

rem BotTG launcher for n8n / manual runs.
rem Starts the API, main bot, scoring service, and admin bot in parallel and writes logs to logs\.

set "ROOT=%~dp0"
cd /d "%ROOT%"

if not exist "logs" mkdir "logs"

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

echo [BotTG] launching with %PYTHON_EXE%

start "" /b cmd /c ""%PYTHON_EXE%" -m uvicorn api.main:app --host 0.0.0.0 --port 8000 >> "logs\api.log" 2>&1"
start "" /b cmd /c ""%PYTHON_EXE%" scoring_service.py >> "logs\scoring_service.log" 2>&1"
start "" /b cmd /c ""%PYTHON_EXE%" main.py >> "logs\main_bot.log" 2>&1"
start "" /b cmd /c ""%PYTHON_EXE%" admin_bot.py >> "logs\admin_bot.log" 2>&1"

echo [BotTG] all modules started in background.
echo [BotTG] logs:
echo   - %ROOT%logs\api.log
echo   - %ROOT%logs\scoring_service.log
echo   - %ROOT%logs\main_bot.log
echo   - %ROOT%logs\admin_bot.log

endlocal
