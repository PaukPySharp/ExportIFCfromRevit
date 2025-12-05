# -*- coding: utf-8 -*-
"""Простые утилиты для запуска CLI и работы с путями (Windows).

Назначение:
    - Преобразование путей с не-ASCII символами в короткий DOS-вариант (8.3).
    - Запуск внешних команд через subprocess.Popen([...]) и построчный вывод
      stdout/stderr в консоль (или колбэк).

Контракты:
    - Ожидается платформа Windows (WinAPI kernel32.GetShortPathNameW).
    - Все публичные функции принимают пути как str или Path.
    - run_cmd_streaming всегда запускает процессы с shell=False и
      объединёнными stdout/stderr.

Особенности:
    - Использует короткие пути (8.3) для минимизации проблем с Unicode
      и пробелами в командной строке.
    - На Windows пытается использовать OEM-кодировку консоли (cp866 и т.п.)
      для корректного чтения русскоязычного вывода.
    - Модуль вызывается только со стороны CPython-оркестратора и
      не импортируется в IronPython-скрипты.
"""
import os
import ctypes
import subprocess
from pathlib import Path
from ctypes import wintypes
from typing import (
    Mapping,
    Optional,
    Callable,
    Sequence,
)

# ---------------------- WinAPI: GetShortPathNameW ----------------------
# Обёртка над WinAPI-функцией получения короткого 8.3-пути.
# Нужна для старых/капризных утилит, которые плохо переваривают Unicode.
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_GetShortPathNameW = _kernel32.GetShortPathNameW
_GetShortPathNameW.argtypes = (
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    wintypes.DWORD,
)
_GetShortPathNameW.restype = wintypes.DWORD
# 260 — исторический лимит для типичных WinAPI-буферов.
_MAX_PATH = 260


# ---------------------- Вспомогательные: ASCII ----------------------
def has_non_ascii(text: str) -> bool:
    """Проверяет, содержит ли строка символы вне ASCII-диапазона.

    :param text: Входная строка.
    :return:     True, если есть символы c кодом > 127; иначе False.
    """
    return any(ord(ch) > 127 for ch in text)


# ----------------------- Вспомогательные: пути -----------------------
def get_short_path(path: str | Path) -> str:
    """Возвращает короткий DOS-путь (8.3) для существующего пути.

    Если преобразование невозможно или путь не существует —
    возвращается исходный путь.

    :param path: Абсолютный/относительный путь (str или Path).
    :return:     Короткий путь 8.3 либо исходный путь.
    """
    s = str(path)

    # Если файл/папка не существуют — WinAPI всё равно не поможет.
    # Сразу отдаём исходный путь.
    if not os.path.exists(s):
        return s

    # Выделяем фиксированный буфер под результат.
    buffer = ctypes.create_unicode_buffer(_MAX_PATH)
    result = _GetShortPathNameW(s, buffer, _MAX_PATH)

    # При неуспехе WinAPI возвращаем исходный путь — не ломаем вызывающий код.
    return buffer.value if result else s


def safe_path(path: str | Path, force: bool = False) -> str:
    """Возвращает «безопасный» путь для Windows CLI.

    Правила:
        - Если в пути есть не-ASCII символы → используем короткий путь (8.3).
        - При force=True короткий путь возвращается всегда (если возможно).

    :param path:  Абсолютный/относительный путь.
    :param force: Принудительное преобразование в короткий путь при
                  возможности.
    :return:      Строка безопасного пути.
    """
    s = str(path)

    # В обычном режиме бережно относимся к путям:
    # конвертируем только «рискованные» (с не-ASCII символами).
    if force or has_non_ascii(s):
        return get_short_path(s)
    return s


# --------------------- Вспомогательные: процессы ---------------------
def run_cmd_streaming(
    cmd: Sequence[str],
    cwd: Optional[str] = None,
    env_add: Optional[Mapping[str, str]] = None,
    echo_cmd: bool = True,
    timeout: Optional[float] = None,
    on_line: Optional[Callable[[str], None]] = None,
) -> int:
    """Запускает команду и построчно транслирует stdout+stderr.

    Назначение:
        - Простая обёртка над subprocess.Popen, которая:
            * выводит команду (по желанию),
            * сливает stdout и stderr,
            * читает вывод построчно и прокидывает его в on_line или print.

    Контракты:
        - shell=False;
        - stdout и stderr объединены (сохраняем порядок);
        - на Windows вывод декодируется по OEM-кодировке консоли
          (cp866 и т.п.), чтобы корректно отображалась кириллица.

    :param cmd:      Команда для запуска в виде последовательности
                     аргументов.
    :param cwd:      Рабочая директория процесса или None (по умолчанию —
                     текущая).
    :param env_add:  Дополнительные переменные окружения, которые нужно
                     добавить к текущему окружению.
    :param echo_cmd: Вывести команду перед запуском, если True.
    :param timeout:  Таймаут в секундах на завершение процесса. При
                     превышении процесс принудительно завершается, а код
                     возврата будет -9.
    :param on_line:  Колбэк, вызываемый для каждой строки вывода. Если не
                     задан, строки печатаются через print().
    :return:         Код возврата процесса (0 — успех; ненулевое значение
                     означает ошибку).
    """

    # 1. Локальный helper вывода строки (колбэк или stdout).
    def _push(line: str):
        """Передаёт строку в on_line или печатает в stdout.

        :param line: Строка вывода процесса без завершающих символов
                     перевода строки.
        """
        if on_line:
            on_line(line)
        else:
            print(line)

    # 2. Готовим список аргументов и echo-строку команды.
    # Приводим команду к списку — subprocess.Popen ожидает последовательность.
    cmd_list = list(cmd)
    # По желанию «эхо» команды перед запуском (для логов/отладки).
    if echo_cmd:
        pretty = " ".join(
            f'"{c}"'
            if " " in c
            else str(c)
            for c in cmd_list
        )
        _push(f"[run] {pretty}")

    # 3. Собираем окружение процесса (текущее + env_add).
    # Базовое окружение — текущее окружение процесса.
    env = os.environ.copy()
    # env_add дополняет (или переопределяет) переменные.
    if env_add:
        env.update(env_add)

    # 4. Определяем кодировку для вывода (Windows: OEM кодировка консоли).
    #    На *nix encoding оставляем None, используется locale по умолчанию.
    encoding: Optional[str] = None
    if os.name == "nt":
        try:
            # OEM-кодировка консоли (обычно cp866 на русской Windows).
            codepage = ctypes.windll.kernel32.GetOEMCP()
            if codepage:
                encoding = f"cp{codepage}"
        except Exception:
            encoding = None

    # 5. Запускаем процесс. stdout и stderr объединены в один поток,
    #    текстовый режим + построчный буфер.
    proc = subprocess.Popen(
        cmd_list,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding=encoding,
        errors="replace",
        bufsize=1,  # построчно
        universal_newlines=True,
        shell=False,
    )

    try:
        # 6. Читаем вывод построчно и транслируем наружу.
        if proc.stdout is not None:
            for raw in proc.stdout:
                line = raw.rstrip("\r\n")
                _push(line)

        # 7. Ожидаем завершения процесса, учитывая таймаут.
        rc = 0
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # При таймауте пробуем аккуратно завершить процесс и
            # возвращаем специальный код -9.
            _push("[run] timeout, terminating process...")
            try:
                proc.kill()
            except Exception:
                # Если завершить не удалось, просто игнорируем —
                # код возврата всё равно остаётся -9.
                pass
            rc = -9

        return rc

    finally:
        # 8. Гарантированно закрываем stdout, чтобы не держать дескриптор.
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass
