# -*- coding: utf-8 -*-
"""Публичный API пакета config.

Назначение:
    - Собирает в одном месте всё, что нужно остальному коду.
    - Позволяет не думать, в каком именно файле лежит константа или путь.
"""

# Важно: импорты ниже используются через __all__ как публичный API,
# поэтому для этого модуля предупреждения вида "unused-import" считаем
# некорректными.

from .settings import SETTINGS
from .paths import (
    DIR_LOGS,
    DIR_SCRIPTS,
    DIR_HISTORY,
    DIR_ADMIN_DATA,
    DIR_EXPORT_CONFIG,
)
from .files import (
    MANAGE_PATH,
    HISTORY_PATH,
    SCRIPT_EXPORT_IFC,
    JSON_CONFIG_FILENAME,
    build_task_path,
    build_csv_path,
)
from .constants import (
    MANAGE_NAME,
    LOGGER_NAME,
    HISTORY_NAME,
    FORMAT_DATETIME,
)

REVIT_VERSIONS = SETTINGS.revit_versions
"""Список поддерживаемых версий Revit (int)."""

FLAG_UNMAPPED = SETTINGS.enable_unmapped_export
"""Флаг выгрузки дополнительного IFC без маппирования."""

# ----------------------- листы Excel (задаются в ini) ------------------------
SHEET_PATH = SETTINGS.sheet_path
"""Лист Excel с путями/настройками."""

SHEET_IGNORE = SETTINGS.sheet_ignore
"""Лист Excel с игнор-списком."""

SHEET_HISTORY = SETTINGS.sheet_history
"""Лист Excel с историей запусков скрипта."""

# ----------------- имена подпапок маппинга (задаются в ini) ------------------
DIR_MAPPING_COMMON = SETTINGS.mapping_dir_common
"""Имя подпапки маппинга общих настроек (без маппинга)."""

DIR_MAPPING_LAYERS = SETTINGS.mapping_dir_layers
"""Имя подпапки маппинга категорий Revit → IFC."""


__all__ = [
    # фасад настроек
    "SETTINGS",
    # ревит и флаги
    "REVIT_VERSIONS",
    "FLAG_UNMAPPED",
    # формат даты/времени
    "FORMAT_DATETIME",
    # имя логгера
    "LOGGER_NAME",
    # названия управляющих файлов
    "MANAGE_NAME",
    "HISTORY_NAME",
    # подпапки маппинга
    "DIR_MAPPING_COMMON",
    "DIR_MAPPING_LAYERS",
    # пути/файлы
    "JSON_CONFIG_FILENAME",
    "SCRIPT_EXPORT_IFC",
    "SHEET_PATH",
    "SHEET_IGNORE",
    "SHEET_HISTORY",
    "MANAGE_PATH",
    "HISTORY_PATH",
    "DIR_EXPORT_CONFIG",
    "DIR_ADMIN_DATA",
    "DIR_LOGS",
    "DIR_HISTORY",
    "DIR_SCRIPTS",
    # утилиты
    "build_task_path",
    "build_csv_path",
]
