# -*- coding: utf-8 -*-
"""Хелперы для работы с файловой системой.

Назначение:
    - Создание директории по пути (если нужно).
    - Нормализация путей (resolve_if_exists).
    - Получение времени модификации файла.
    - Нормализация времени модификации «до минут».

Контракты:
    - Все функции принимают как Path, так и str (через PathLike).
    - Ошибки доступа к файлам/директориям не должны ронять процесс:
        * file_mtime / file_mtime_minute возвращают None;
        * resolve_if_exists возвращает исходный path без исключений.

Особенности:
    - Время модификации файлов возвращается как naive datetime в локальном
      часовом поясе.
    - file_mtime_minute отбрасывает секунды и микросекунды для унификации
      сравнения дат «до минут» во всём проекте.
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Union, overload

from utils.compat import ensure_dir_compat

# Разрешаем передавать как Path, так и str
PathLike = Union[str, Path]


# ----------------------------- каталоги -----------------------------
def ensure_dir(path: Optional[PathLike]) -> Optional[Path]:
    """Создаёт директорию, если путь задан.

    Правила:
        - Если путь None — ничего не делает и возвращает None.
        - Если путь строка — приводится к Path.
        - mkdir(parents=True, exist_ok=True) — идемпотентно:
          существующая директория не считается ошибкой.

    :param path: Путь к директории или None.
    :return:  Нормализованный Path или None (если путь не задан).
    """
    return ensure_dir_compat(path)


# Перегрузки нужны только для статического анализа типов (MyPy/Pylance):
#   None      -> None
#   PathLike  -> Path
# В рантайме вызывается только реализация ниже; эти заглушки не
# исполняются и не должны удаляться как "лишний" код.
@overload
def resolve_if_exists(path: None) -> None: ...
@overload
def resolve_if_exists(path: PathLike) -> Path: ...


def resolve_if_exists(path: Optional[PathLike]) -> Optional[Path]:
    """Нормализует путь (resolve), если он задан и существует.

    Правила:
        - None → None;
        - если путь существует → возвращается path.resolve() с
          расширением в нижнем регистре;
        - если не существует → возвращается исходный путь в виде Path
          (без исключений).

    :param path: Путь к файлу/директории (str или Path) либо None.
    :return:     Нормализованный Path или None.
    """
    if path is None:
        return None

    # Всегда приводим к Path
    path_obj = path if isinstance(path, Path) else Path(path)
    try:
        if not path_obj.exists():
            return path_obj
        # нормализуем путь и возвращаем с расширением в нижнем регистре
        resolved = path_obj.resolve()
        if resolved.suffix:
            return resolved.with_suffix(resolved.suffix.lower())
    except OSError:
        # В случае ошибки тоже возвращаем Path
        return path_obj


# ----------------------------- даты модификации -----------------------------
def file_mtime(path: PathLike) -> Optional[datetime]:
    """Возвращает локальное время модификации файла.

    Особенности:
        - Значение берётся из path.stat().st_mtime (секунды с эпохи).
        - Возвращается naive datetime в локальном часовом поясе.
        - При ошибке (нет файла, нет прав и т.п.) возвращает None.

    :param path: Путь к файлу (Path или str).
    :return:     datetime (локальное время), либо None при
                 ошибке/недоступности.
    """
    p = Path(path)
    try:
        mtime = p.stat().st_mtime
        return datetime.fromtimestamp(mtime)
    except Exception:
        return None


def file_mtime_minute(path: PathLike) -> Optional[datetime]:
    """Возвращает время модификации файла, округлённое до минут.

    Используется для унификации дат при сравнении истории и целевых файлов:
    секунды/микросекунды отбрасываются, чтобы избежать «шума» при сравнении.

    :param path: Путь к файлу (Path или str).
    :return:     datetime без секунд/микросекунд, либо None.
    """
    dt = file_mtime(path)
    if dt is None:
        return None

    # Отсекаем "шум" секунд и микросекунд — важно при сравнении дат и логах.
    return dt.replace(second=0, microsecond=0)
