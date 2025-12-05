# -*- coding: utf-8 -*-
"""Хелперы для текстовых логов (Windows).

Назначение:
    - Запись набора строк в txt-лог с опциональным суффиксом даты.

Контракты:
    - write_log_lines():
        * гарантирует наличие директории log_dir (создаёт при необходимости);
        * формирует имя файла на основе base_name и, при add_date_suffix=True,
          добавляет суффикс текущей даты в формате FORMAT_DATE_LOG;
        * ожидает, что элементы в lines не содержат завершающего '\\n' —
          перевод строки добавляется функцией;
        * если separator непустой, то после всех строк записывается
          разделитель и перевод строки.
    - append_log_separator():
        * работает только с датированным именем файла
          "<base_name>_<YYYY.MM.DD>.txt";
        * если файл ещё не существует или separator пустой — ничего не делает;
        * добавляет одну строку-разделитель в конец файла без лишних
          пустых строк.

Особенности:
    - Модуль может выполняться под IronPython 3.4 (pyRevit).
    - Допускается использование модуля typing для аннотаций типов, но без
      современного синтаксиса, требующего более новых версий Python
      (list[str], X | Y и т.п.) в исполняемом коде.
"""
from pathlib import Path
from typing import Iterable
from datetime import datetime

from config.constants import FORMAT_DATE_LOG

from utils.files import ensure_ext
from utils.compat import ensure_dir_compat

# Стандартный разделитель блоков в txt-логах.
# Если захочется другой формат (например, с датой/временем) —
# достаточно поменять эту константу.
LOG_SEPARATOR = "-" * 50


# ---------------------- внутренние хелперы ----------------------
def _build_log_path(
    log_dir: Path,
    base_name: str,
    add_date_suffix: bool,
    date_fmt: str,
) -> Path:
    """Формирует путь к txt-логу с учётом суффикса даты.

    Логика имени:
        - При add_date_suffix=True → "<base_name>_<YYYY.MM.DD>.txt";
        - Иначе → "<base_name>.txt".

    :param log_dir:         Папка для логов.
    :param base_name:       Базовое имя лога без расширения.
    :param add_date_suffix: Добавлять ли суффикс текущей даты к имени файла.
    :param date_fmt:        Формат даты для суффикса.
    :return:                Полный Path к файлу лога.
    """
    if add_date_suffix:
        date = datetime.now().strftime(date_fmt)
        name = f"{base_name}_{date}"
    else:
        name = base_name

    # ensure_ext гарантирует расширение .txt, даже если base_name уже с ним.
    filename = ensure_ext(name, ".txt")
    return log_dir / filename


# ---------------------- Публичное API ----------------------
def write_log_lines(
    log_dir: Path,
    base_name: str,
    lines: Iterable[str],
    *,
    add_date_suffix: bool = True,
    date_fmt: str = FORMAT_DATE_LOG,
    separator: str = LOG_SEPARATOR,
    encoding: str = "utf-8",
    mode: str = "a",
) -> None:
    """Пишет строки в текстовый лог.

    Имена файлов:
        - При add_date_suffix=True → "<base_name>_<YYYY.MM.DD>.txt"
        - Иначе → "<base_name>.txt"

    :param log_dir:         Папка для логов (будет создана при необходимости).
    :param base_name:       Базовое имя лога без расширения.
    :param lines:           Итератор строк без завершающего '\\n'.
    :param add_date_suffix: Добавлять ли суффикс текущей даты к имени файла.
    :param date_fmt:        Формат даты для суффикса.
    :param separator:       Разделитель, пишется в конце блока (пустая строка —
                            чтобы не писать).
    :param encoding:        Кодировка файла.
    :param mode:            Режим записи: 'a' — дописывать, 'w' —
                            перезаписывать.
    """
    # 1. Гарантируем наличие целевой директории.
    ensure_dir_compat(log_dir)

    # 2. Строим путь к файлу лога (с датой или без — по флагу).
    path = _build_log_path(log_dir, base_name, add_date_suffix, date_fmt)

    # 3. Пишем строки. newline="" — чтобы не плодить лишние пустые строки:
    #    сами добавляем '\n' в конце каждой строки.
    with open(str(path), mode, encoding=encoding, newline="") as f:
        for line in lines:
            f.write(f"{line}\n")
        if separator:
            f.write(f"{separator}\n")


def append_log_separator(
    log_dir: Path,
    base_name: str,
    *,
    date_fmt: str = FORMAT_DATE_LOG,
    separator: str = LOG_SEPARATOR,
    encoding: str = "utf-8",
) -> None:
    """Добавляет разделитель в конец существующего датированного лога.

    Используется для логов pyRevit (1_/2_*.txt), где строки могут
    дописываться из нескольких процессов, а разделитель нужно ставить
    один раз на запуск оркестратора.

    Если файл ещё не существует или separator пустой — ничего не делает.

    :param log_dir:   Папка для логов.
    :param base_name: Базовое имя лога без расширения.
    :param date_fmt:  Формат даты для суффикса имени файла.
    :param separator: Строка-разделитель.
    :param encoding:  Кодировка файла.
    """
    if not separator:
        return

    # Для разделителей всегда работаем с датированным именем,
    # чтобы попасть в тот же файл, что и write_log_lines() с настройками
    # по умолчанию.
    path = _build_log_path(log_dir, base_name, True, date_fmt)

    if not path.exists():
        return

    with open(str(path), "a", encoding=encoding, newline="") as f:
        f.write(f"{separator}\n")
