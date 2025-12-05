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
import threading
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
# 32767 — максимальная длина NT-пути в Unicode-версии WinAPI (включая NUL).
_MAX_UNICODE_PATH = 32767


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

    # GetShortPathNameW возвращает требуемый размер буфера, поэтому
    # повторяем вызов при нехватке места (длинные пути > 260 символов).
    # Ограничиваемся максимальной длиной NT-пути, чтобы не уйти в бесконечное
    # выделение гигантских буферов при некорректном ответе WinAPI.
    buf_size = _MAX_PATH
    while buf_size <= _MAX_UNICODE_PATH:
        buffer = ctypes.create_unicode_buffer(buf_size)
        result = _GetShortPathNameW(s, buffer, buf_size)

        # 0 — ошибка WinAPI (например, нет прав); отдаём исходный путь.
        if result == 0:
            return s

        # Если буфер мал, WinAPI сообщает требуемый размер (без учёта NUL).
        if result >= buf_size:
            buf_size = result + 1
            continue

        return buffer.value

    # Перебрали разумные размеры — безопасно возвращаем исходный путь.
    return s


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
            * читает вывод построчно в отдельном потоке и прокидывает его
              в on_line или print, чтобы ожидание с таймаутом не блокировалось
              на буферизованном stdout.

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
    cmd_list = list(cmd)
    if echo_cmd:
        _push(f"[run] {_format_command(cmd_list)}")

    # 3. Собираем окружение процесса (текущее + env_add).
    env = _prepare_env(env_add)

    # 4. Определяем кодировку для вывода (Windows: OEM кодировка консоли).
    encoding: Optional[str] = _detect_windows_encoding()

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

    # Отдельный поток читает stdout, чтобы proc.wait(timeout) не зависал
    # из-за переполнения буфера вывода.
    reader = _start_stdout_reader(proc, _push)

    try:
        # 6. Ожидаем завершения процесса, учитывая таймаут.
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

            # Дожидаемся завершения процесса после kill(), чтобы не оставлять
            # зомби/висящие дескрипторы. Не меняем rc, даже если wait()
            # вернул другой код или снова выбросил исключение.
            try:
                proc.wait(timeout=1)
            except Exception:
                pass

            rc = -9

        return rc

    finally:
        # 7. Гарантированно закрываем stdout и дожидаемся
        #    завершения потокового читателя, чтобы не утекали дескрипторы.
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass

        # reader — daemon, но join ускоряет уборку между последующими вызовами.
        reader.join(timeout=1)


def _detect_windows_encoding() -> Optional[str]:
    """Определяет OEM-кодировку консоли Windows для корректного вывода.

    :return: Строка вида "cp866"/"cp1251" и т.п. или None, если
             определение невозможно или платформа не Windows.
    """

    if os.name != "nt":
        return None

    try:
        # OEM-кодировка консоли (cp866 и т.п.) подходит для stdout CLI-утилит.
        codepage = ctypes.windll.kernel32.GetOEMCP()
        if codepage:
            return f"cp{codepage}"
    except Exception:
        return None


def _prepare_env(env_add: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    """Возвращает окружение для дочернего процесса.

    :param env_add: Дополнительные переменные, которые нужно добавить к
                    текущему окружению.
    :return:        Новый словарь окружения (копия os.environ с
                    применёнными env_add).
    """
    # Базовое окружение — текущее окружение процесса.
    env = os.environ.copy()
    if env_add:
        # env_add дополняет (или переопределяет) переменные.
        env.update(env_add)
    return env


def _format_command(cmd_list: Sequence[str]) -> str:
    """Человекочитаемое представление команды для логирования.

    :param cmd_list: Последовательность аргументов команды.
    :return:         Строка с экранированием пробельных аргументов
                     кавычками для удобного вывода.
    """

    # Добавляем кавычки только к аргументам с пробелами — читаемость в логе.
    return " ".join(
        f'"{c}"' if " " in c else str(c)
        for c in cmd_list
    )


def _start_stdout_reader(
    proc: subprocess.Popen,
    push: Callable[[str], None]
) -> threading.Thread:
    """Запускает поток, читающий stdout процесса.

    :param proc: Процесс, stdout которого нужно читать.
    :param push: Колбэк, принимающий строки вывода (без CR/LF).
    :return:     Запущенный поток-читатель (daemon=True).
    """

    def _consume_stdout() -> None:
        """Читает stdout процесса построчно в отдельном потоке.

        Поток блокируется на чтении `.stdout`, чтобы основной поток мог
        управлять таймаутом/kill без риска зависнуть на буферизованном
        выводе. Каждая строка передаётся в `push` после удаления
        завершающих `\r`/`\n`.

        :return: None.
        """

        if proc.stdout is None:
            return
        for raw in proc.stdout:
            # .rstrip() убирает CR/LF, оставляя «голый» текст строки.
            line = raw.rstrip("\r\n")
            push(line)

    reader = threading.Thread(target=_consume_stdout, daemon=True)
    reader.start()
    return reader
