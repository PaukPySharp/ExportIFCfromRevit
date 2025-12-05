@echo off
chcp 65001 >nul
setlocal

REM ==================== НАСТРОЙКИ СКРИПТА ====================
REM Основной вариант:
REM   просим Python-лаунчер запустить ЛЮБУЮ установленную Python 3.x.
REM   Обычно этого достаточно.
set "PYTHON_VERSION=3"

REM Если на компьютере установлено несколько версий Python 3.x
REM и нужные библиотеки (например, openpyxl) стоят только в одной
REM из них, можно указать конкретную версию.
REM По умолчанию используется любая версия Python 3 (строка выше).
REM Чтобы задать конкретную:
REM   1) Удалите "REM " в начале нужной строки set "PYTHON_VERSION=..."
REM   2) При желании добавьте "REM " в начало строки set "PYTHON_VERSION=3"
REM Примеры строк, которые можно включить:
REM set "PYTHON_VERSION=3.12"
REM set "PYTHON_VERSION=3.13"

REM Команда запуска Python.
REM Обычно это "py". При необходимости можно заменить на "python"
REM или полный путь к конкретному интерпретатору.
set "PY_CMD=py"

REM Путь к main.py относительно текущей bat-папки:
REM   _settings\bat -> ..\.. -> корень проекта ExportIFCfromRevit
set "MAIN_PY=%~dp0..\..\main.py"

REM Нормализуем путь к main.py в полный абсолютный
for %%I in ("%MAIN_PY%") do set "MAIN_PY=%%~fI"

REM Код возврата по умолчанию (на случай раннего выхода по ошибке).
set "EXITCODE=1"
REM ============================================================

REM Определяем фактическую версию Python,
REM которая реально запустится через "%PY_CMD% -%PYTHON_VERSION%".
set "PY_ACTUAL_VERSION="

for /f "tokens=2" %%V in ('
    "%PY_CMD%" -%PYTHON_VERSION% --version
') do (
    set "PY_ACTUAL_VERSION=%%V"
)

REM Если по какой-то причине версию вытащить не получилось,
REM показываем хотя бы общую маску вроде "3.x".
if not defined PY_ACTUAL_VERSION (
    set "PY_ACTUAL_VERSION=%PYTHON_VERSION%.x"
)

REM ---------- 0. Проверка наличия main.py ----------
echo [Шаг 0] Проверка наличия main.py по пути:
echo          %MAIN_PY%
if not exist "%MAIN_PY%" (
    echo [ОШИБКА] Не найден main.py по указанному пути.
    goto FINISH
)

REM ---------- 1. Запуск сценария по экспорту IFC ----------
echo [Шаг 1] Запуск экспорта IFC (Python %PY_ACTUAL_VERSION%)...
echo.
"%PY_CMD%" -%PYTHON_VERSION% "%MAIN_PY%"
set "EXITCODE=%ERRORLEVEL%"

if %EXITCODE% EQU 0 (
    echo [OK] Экспорт IFC завершился успешно.
) else (
    echo [ОШИБКА] Экспорт IFC завершился с кодом %EXITCODE%.
)

REM ---------- Завершение ----------
:FINISH
echo.
echo Скрипт завершил работу. Код: %EXITCODE%.
echo Нажмите любую клавишу или окно закроется автоматически через 5 минут...
timeout /t 600 >nul

endlocal & exit /b %EXITCODE%
