@echo off
echo ===================================
echo  Admin Bot - @zhiizn_admin_bot
echo ===================================
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не найден!
    pause
    exit /b 1
)

REM Запуск admin bot
echo Запуск admin bot...
python admin_bot.py

pause
