# -*- coding: utf-8 -*-
"""Производные пути и рабочие папки проекта.

Назначение:
    - Формирует абсолютные пути к ключевым директориям проекта.
    - Учитывает режим работы (prod/test) и собирает единый набор DIR_*.

Контракты:
    - Никаких директорий здесь не создаётся — только формирование путей.
    - Корень проекта определяется Settings.main_dir.
    - В режиме prod пути берутся из settings.ini как есть.
    - В тестовом режиме admin_data разворачивается локально внутри
      DIR_SCRIPTS/admin_data.
    - При импорте модуля проверяется существование DIR_EXPORT_CONFIG и
      DIR_ADMIN_DATA;
      при ошибке конфигурации поднимается FileNotFoundError/NotADirectoryError.

Особенности:
    - Логи и история хранятся в подпапках внутри DIR_ADMIN_DATA.
"""
from pathlib import Path

from config.settings import SETTINGS as STG
from config.constants import ADMIN_DATA_NAME


def _assert_dir_exists(path: Path, name: str) -> Path:
    """Проверяет, что указанный путь существует и является директорией.

    :param path: Путь, полученный из настроек или вычисленный на основе них.
    :param name: Имя настройки или человекочитаемый ярлык директории
                 (используется только в тексте ошибки).
    :raises FileNotFoundError: если путь не существует.
    :raises NotADirectoryError: если путь существует, но не является папкой.
    :return: Тот же Path, если проверка прошла успешно.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"В настройках указан путь '{name}' = {path}, "
            f"но такой директории не существует. "
            f"Проверь settings.ini (секция [Paths])."
        )
    if not path.is_dir():
        raise NotADirectoryError(
            f"В настройках '{name}' = {path}, "
            f"но это не директория. Ожидалась папка."
        )
    return path


# ----------------------------- режим работы -----------------------------
IS_PROD_MODE: bool = STG.is_prod_mode
"""True — production-режим; False — тестовый режим."""

# ----------------------------- базовые папки -----------------------------
DIR_SCRIPTS: Path = Path(STG.dir_scripts)
"""Корень скриптов проекта (совпадает с main_dir)."""

DIR_EXPORT_CONFIG: Path = _assert_dir_exists(
    Path(STG.dir_export_config), "dir_export_config")
"""Директория с маппинг-файлами (слои/настройки)."""

# ----------------------------- admin_data -----------------------------
# В production используем dir_admin_data из настроек.
# В test-режиме разворачиваем admin_data локально рядом со скриптами.
_admin_data_base: Path = (
    Path(STG.dir_admin_data)
    if IS_PROD_MODE
    else DIR_SCRIPTS / ADMIN_DATA_NAME
)

DIR_ADMIN_DATA: Path = _assert_dir_exists(_admin_data_base, "dir_admin_data")
"""
Базовая директория admin_data:
    - в prod может быть сетевой/общей;
    - в test — локальная папка внутри DIR_SCRIPTS/admin_data.
"""

# ------------- вспомогательные папки внутри admin_data -------------
DIR_LOGS: Path = DIR_ADMIN_DATA / "_logs"
"""Папка для логов выполнения."""

DIR_HISTORY: Path = DIR_ADMIN_DATA / "history"
"""Папка для истории запусков/выгрузок."""
