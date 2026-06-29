@echo off
echo ===================================
echo  AI Content Platform - Unified Bot
echo ===================================
echo.
echo  Контент-бот: @zhiizn_ai
echo  Админ-бот: @zhiizn_admin_bot
echo.
echo  Управление: /start_bot в @zhiizn_admin_bot
echo ===================================
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не найден!
    pause
    exit /b 1
)

REM Запуск
python run_all.py

pause
