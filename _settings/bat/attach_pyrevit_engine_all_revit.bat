@echo off
chcp 65001 >nul
setlocal

REM ==================== НАСТРОЙКИ СКРИПТА ====================
REM PYREVIT_CLI — команда/утилита pyRevit в системе.
REM Если pyrevit прописан в PATH, можно оставить как есть.
REM Если нет — укажите полный путь к pyrevit.exe.
set "PYREVIT_CLI=pyrevit"

REM PYREVIT_CLONE — имя набора pyRevit (clone), который нужно подключить к Revit.
REM По умолчанию стандартный набор называется "master".
set "PYREVIT_CLONE=master"

REM PYREVIT_ENGINE — номер движка (IronPython engine), который будет использоваться.
REM Например: 342 для IronPython 3.4.2.
REM При смене движка достаточно поменять только это число.
set "PYREVIT_ENGINE=342"

REM Код возврата по умолчанию (на случай раннего выхода по ошибке).
set "EXITCODE=1"
REM ============================================================

echo.
echo Настройка pyRevit для всех установленных версий Revit.
echo Будет использован набор "%PYREVIT_CLONE%" и движок IronPython %PYREVIT_ENGINE%.
echo.

REM ---------- 0. Проверка доступности pyRevit CLI ----------
echo [Шаг 0] Проверка доступности команды "%PYREVIT_CLI%"...
"%PYREVIT_CLI%" --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ОШИБКА] Команда "%PYREVIT_CLI%" недоступна или вернула ошибку.
    echo Убедитесь, что:
    echo   - pyRevit установлен;
    echo   - команда "%PYREVIT_CLI%" доступна в командной строке;
    echo   - переменная PATH настроена корректно.
    goto FINISH
)

REM ---------- 1. Подключение pyRevit ко всем Revit ----------
echo [Шаг 1] Подключение pyRevit ко всем установленным Revit...
REM   - PYREVIT_CLONE  -> какой набор pyRevit подключаем (master)
REM   - PYREVIT_ENGINE -> какой движок IronPython использовать (342)
REM   - --installed    -> применить ко всем установленным версиям Revit
"%PYREVIT_CLI%" attach "%PYREVIT_CLONE%" %PYREVIT_ENGINE% --installed

REM Сохраняем код возврата команды pyRevit.
set "EXITCODE=%ERRORLEVEL%"
echo.

REM Разбираем результат:
REM   0   -> команда отработала без критических ошибок
REM   !=0 -> pyRevit сообщил об ошибке (подробности были выше в выводе)
if %EXITCODE% EQU 0 (
    echo [OK] pyRevit успешно подключён ко всем установленным Revit.
    echo Используется набор "%PYREVIT_CLONE%" и движок IronPython %PYREVIT_ENGINE%.
) else (
    echo [ОШИБКА] Команда pyRevit завершилась с кодом %EXITCODE%.
    echo Проверьте, что:
    echo   - pyRevit установлен;
    echo   - команда "%PYREVIT_CLI%" доступна в командной строке;
    echo   - номер движка %PYREVIT_ENGINE% поддерживается установленной версией pyRevit.
)

REM ---------- Завершение ----------
:FINISH
echo.
echo Скрипт завершил работу. Код: %EXITCODE%.
echo Нажмите любую клавишу для выхода...
pause >nul

endlocal & exit /b %EXITCODE%

