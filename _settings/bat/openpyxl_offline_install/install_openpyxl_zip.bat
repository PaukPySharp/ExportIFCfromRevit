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

REM Имя пакета, который устанавливаем.
set "PACKAGE_NAME=openpyxl"

REM Путь к архиву openpyxl.zip с пакетами для офлайн-установки.
REM Текущая папка bat-файла:
REM   _settings\bat\openpyxl_offline_install
REM Переход к корню проекта и далее в _for_python\openpyxl.zip:
REM   ..\..\..\_for_python\openpyxl.zip
set "ARCHIVE_PATH=%~dp0..\..\..\_for_python\openpyxl.zip"
for %%I in ("%ARCHIVE_PATH%") do set "ARCHIVE_PATH=%%~fI"

REM Вспомогательный Python-скрипт, который распаковывает архив в site-packages.
REM Лежит рядом с этим bat-файлом и называется _install_openpyxl_zip.py.
set "INSTALL_PY=%~dp0_install_openpyxl_zip.py"

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

echo Оффлайн-установка %PACKAGE_NAME% (Python %PY_ACTUAL_VERSION%)...
echo.

REM ---------- Шаг 0. Проверка наличия архива ----------
echo [Шаг 0] Проверка наличия архива с пакетами:
echo          %ARCHIVE_PATH%
if not exist "%ARCHIVE_PATH%" (
    echo [ОШИБКА] Архив не найден по указанному пути.
    goto FINISH
)

REM ---------- Шаг 1. Проверка вспомогательного скрипта ----------
echo [Шаг 1] Проверка файла _install_openpyxl_zip.py:
echo          %INSTALL_PY%
if not exist "%INSTALL_PY%" (
    echo [ОШИБКА] Не найден вспомогательный скрипт:
    echo          %INSTALL_PY%
    goto FINISH
)

REM ---------- Шаг 2. Запуск офлайн-установки ----------
echo [Шаг 2] Распаковка архива в каталог site-packages текущего Python...
"%PY_CMD%" -%PYTHON_VERSION% "%INSTALL_PY%" "%ARCHIVE_PATH%"
set "EXITCODE=%ERRORLEVEL%"
echo.

if %EXITCODE% EQU 0 (
    echo [OK] Пакеты %PACKAGE_NAME% успешно установлены из архива.
) else (
    echo [ОШИБКА] Офлайн-установка завершилась с кодом %EXITCODE%.
)

REM ---------- Завершение ----------
:FINISH
echo.
echo Скрипт завершил работу. Код: %EXITCODE%.
echo Нажмите любую клавишу для выхода...
pause >nul

endlocal & exit /b %EXITCODE%