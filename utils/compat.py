# -*- coding: utf-8 -*-
"""Совместимые хелперы для IronPython 3.4 и старого CPython.

Назначение:
    - Унифицированная логика для создания директорий с защитой от отсутствия
      параметра exist_ok в Path.mkdir.

Особенности:
    - Модуль может выполняться под IronPython 3.4 (pyRevit).
    - Не используем typing/dataclasses и современный синтаксис типов.
"""

from pathlib import Path


def ensure_dir_compat(p):
    """Создаёт директорию с защитой от отсутствия exist_ok (IronPython).

    Правила:
        - Если p is None → ничего не делает, возвращает None.
        - Если путь не существует → создаёт с parents=True.
        - Защищает от TypeError, если exist_ok не поддерживается.

    :param p: Путь к директории (Path или str).
    :return:  Path или None.
    """
    if p is None:
        return None

    path = Path(p)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except TypeError:
        try:
            path.mkdir(parents=True)
        except Exception:
            if not path.exists():
                raise
    return path
