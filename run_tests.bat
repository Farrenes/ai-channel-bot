@echo off
title Run Bot Tests
chcp 65001 > nul

:: Проверяем наличие venv или .venv
if exist venv\Scripts\activate.bat (
    echo [INFO] Активация окружения venv...
    call venv\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
    echo [INFO] Активация окружения .venv...
    call .venv\Scripts\activate.bat
) else (
    echo [WARNING] Виртуальное окружение не найдено!
)

:: Запуск тестов
python -m pytest test_parsers.py -v
pause
