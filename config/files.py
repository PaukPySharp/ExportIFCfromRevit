# -*- coding: utf-8 -*-
"""Файлы проекта и их абсолютные пути.

Назначение:
    - Хранит имена ключевых файлов (<MANAGE_NAME>.xlsx,
      <HISTORY_NAME>.xlsx, скрипты).
    - Формирует абсолютные пути на основе настроек Settings и структуры
      проекта.

Контракты:
    - Имя JSON-конфигурации берётся из settings.ini (config_json), расширение
      добавляется здесь.
    - Каталоги и файлы в этом модуле не создаются — функции только формируют
      пути.
    - build_task_path формирует путь Task{version}.txt в DIR_ADMIN_DATA.
    - build_csv_path формирует путь <name>.csv в указанной базе
      (по умолчанию DIR_ADMIN_DATA).
"""
from pathlib import Path

from config.settings import SETTINGS as STG
from config.constants import (
    TMP_NAME,
    MANAGE_NAME,
    HISTORY_NAME,
)
from config.paths import (
    DIR_SCRIPTS,
    DIR_HISTORY,
    DIR_ADMIN_DATA,
)

# ----------------------------- базовые имена -----------------------------
JSON_CONFIG_FILENAME: str = f"{STG.config_json}.json"
"""Базовое имя JSON-конфигурации маппинга (без директории)."""

# ----------------------- путь до скрипта экспорта ------------------------
# DIR_SCRIPTS — корень скриптов проекта; ExportIFC.py лежит рядом с main.py
# в той же директории.
SCRIPT_EXPORT_IFC: Path = DIR_SCRIPTS / "ExportIFC.py"
"""Полный путь до скрипта ExportIFC.py (в корне скриптов рядом с main.py)."""

# --------------------------- файлы в admin_data --------------------------
MANAGE_PATH: Path = DIR_ADMIN_DATA / f"{MANAGE_NAME}.xlsx"
"""Путь к управляющей таблице <MANAGE_NAME>.xlsx."""

HISTORY_PATH: Path = DIR_HISTORY / f"{HISTORY_NAME}.xlsx"
"""Путь к файлу истории запусков <HISTORY_NAME>.xlsx."""


# ----- служебные пути в admin_data (Task*.txt, <TMP_NAME>.csv и др.) -----
def build_task_path(version: int) -> Path:
    """Возвращает путь к Task-файлу для указанной версии Revit.

    Формат имени: ``Task{version}.txt``.

    :param version: Версия Revit (например, 2021).
    :return: Абсолютный путь к Task-файлу в директории admin_data.
    """
    return DIR_ADMIN_DATA / f"Task{version}.txt"


def build_csv_path(base_dir: Path = DIR_ADMIN_DATA,
                   name: str = TMP_NAME) -> Path:
    """Возвращает путь к CSV-файлу в указанной директории.

    По умолчанию формирует ``<TMP_NAME>.csv`` в DIR_ADMIN_DATA.

    :param base_dir: Базовая директория, в которой будет лежать CSV-файл.
    :param name:     Имя файла без расширения (например, ``"tmp"``).
    :return:         Абсолютный путь к CSV-файлу (base_dir / f"{name}.csv").
    """
    return base_dir / f"{name}.csv"
