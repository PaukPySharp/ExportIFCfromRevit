@echo off
chcp 65001 >nul
setlocal

REM ==================== НАСТРОЙКИ СКРИПТА ====================
REM Основной вариант:
REM   просим Python-лаунчер запустить ЛЮБУЮ установленную Python 3.x.
REM   Обычно этого достаточно.
set "PYTHON_VERSION=3"

REM Если на компьютере установлено несколько версий Python 3.x
REM и нужные библиотеки стоят только в одной из них,
REM можно указать конкретную версию.
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

REM Путь к локальному каталогу с .whl-файлами относительно этой bat-папки:
REM Текущая папка bat-файла:
REM   _settings\bat
REM Переход к корню проекта и далее в _for_python\openpyxl:
REM   _settings\bat -> ..\..\_for_python\openpyxl
set "WHEELHOUSE_PATH=%~dp0..\..\_for_python\openpyxl"
for %%I in ("%WHEELHOUSE_PATH%") do set "WHEELHOUSE_PATH=%%~fI"

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

echo Установка %PACKAGE_NAME% (Python %PY_ACTUAL_VERSION%)...
echo.

REM ---------- Шаг 0. Проверка, установлен ли уже пакет ----------
echo [Шаг 0] Проверка наличия %PACKAGE_NAME% в текущем Python...
"%PY_CMD%" -%PYTHON_VERSION% -m pip show %PACKAGE_NAME% >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] %PACKAGE_NAME% уже установлен. Повторная установка не требуется.
    set "EXITCODE=0"
    goto FINISH
)

REM ---------- Шаг 1. Попытка установки через pip (онлайн) ----------
echo [Шаг 1] Установка %PACKAGE_NAME% через pip...

REM Если нужно установить пакет в локальную папку пользователя, то
REM раскомментируйте следующую строку, а следующую за ней закомментируйте.
REM "%PY_CMD%" -%PYTHON_VERSION% -m pip install --user %PACKAGE_NAME%
"%PY_CMD%" -%PYTHON_VERSION% -m pip install %PACKAGE_NAME%
set "EXITCODE=%ERRORLEVEL%"
echo.

REM Если pip отработал без ошибок — завершаем работу.
if %EXITCODE% EQU 0 (
    echo [OK] %PACKAGE_NAME% установлен через pip.
    goto FINISH
)

echo [WARN] Установить %PACKAGE_NAME% через pip не удалось (код %EXITCODE%).
echo Перехожу к офлайн-установке из локального каталога .whl...
echo.

REM ---------- Шаг 2. Оффлайн-установка из локального каталога .whl ----------
REM Проверяем существование каталога с .whl-файлами.
echo [Шаг 2] Проверка каталога с .whl-файлами:
echo          %WHEELHOUSE_PATH%
if not exist "%WHEELHOUSE_PATH%" (
    echo [ОШИБКА] Не найден каталог с .whl-файлами.
    set "EXITCODE=1"
    goto FINISH
)

REM ---------- Шаг 3. Установка из локального каталога .whl ----------
echo [Шаг 3] Установка %PACKAGE_NAME% из локального каталога .whl...
echo.

"%PY_CMD%" -%PYTHON_VERSION% -m pip install --no-index --find-links="%WHEELHOUSE_PATH%" %PACKAGE_NAME%
set "EXITCODE=%ERRORLEVEL%"
echo.

if %EXITCODE% EQU 0 (
    echo [OK] %PACKAGE_NAME% установлен из локального каталога .whl.
) else (
    echo [ОШИБКА] Офлайн-установка %PACKAGE_NAME% через .whl завершилась с ошибкой ^(код %EXITCODE%^).
)

REM ---------- Завершение ----------
:FINISH
echo.
echo Скрипт завершил работу. Код: %EXITCODE%.
echo Нажмите любую клавишу для выхода...
pause >nul

endlocal & exit /b %EXITCODE%
