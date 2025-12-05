# -*- coding: utf-8 -*-
"""Глобальные константы конфигурации проекта.

Назначение:
    - Описывает базовые константы, общие для всего проекта.
    - Фиксирует относительные пути к ini и служебным библиотекам.

Контракты:
    - Пути задаются относительно корня проекта (main_dir).
    - Каталоги и файлы здесь не создаются, только формируются строки.
"""

TMP_NAME = "tmp"
"""Базовое имя временных файлов (временный CSV: TMP_NAME + ".csv")."""

MANAGE_NAME = "manage"
"""Базовое имя управляющей таблицы (имя файла: MANAGE_NAME + ".xlsx")."""

HISTORY_NAME = "history"
"""Базовое имя файла истории запусков (имя файла: HISTORY_NAME + ".xlsx")."""

LOGGER_NAME = "export_ifc"
"""Имя корневого логгера приложения."""

ADMIN_DATA_NAME = 'admin_data'
"""Имя каталога с административными файлами (внешним оркестратором)."""

SETTINGS_DIR = "_settings"
"""Папка, где хранятся конфигурационные и служебные файлы проекта."""

SETTINGS_INI = f"{SETTINGS_DIR}/settings.ini"
"""Относительный путь к основному ini-файлу настроек."""

IFC_EXPORTER_DLL = f"{SETTINGS_DIR}/ApiIFCExporter/Autodesk.IFC.Export.UI.dll"
"""Относительный путь к DLL 'IFC.Export.UI' (для подключения через clr)."""

FORMAT_DATETIME = "%Y-%m-%d %H:%M"
"""Формат даты/времени для datetime.strptime/strftime: YYYY-MM-DD HH:MM."""

FORMAT_DATE_LOG = "%Y.%m.%d"
"""Формат даты для имён файлов логов: YYYY.MM.DD."""

# ---------------------- базовые имена файлов txt-логов -----------------------
LOGFILE_OPENING_ERRORS = "1_errors_when_opening_models"
"""Лог ошибок при открытии моделей в Revit."""

LOGFILE_MISSING_VIEW_TEMPLATE = "2_not_view_$$$_in_models"
"""Шаблон базового имени лог-файла моделей без 3D-вида для экспорта IFC.

Подстрока "$$$" будет заменена на имя вида из настроек
(раздел [Revit], параметр export_view3d_name).
"""

LOGFILE_VERSION_NOT_FOUND = "3_not_found_versions"
"""Лог случаев, когда не удалось определить версию Revit."""

LOGFILE_VERSION_TOO_NEW = "4_not_supported_versions"
"""Лог моделей с версией Revit выше поддерживаемого диапазона."""

LOGFILE_EXPORT_ERRORS = "5_export_errors"
"""Лог ошибок при экспорте моделей."""

LOGFILE_MTIME_ISSUES = "6_mtime_issues"
"""Лог проблем с mtime моделей (нестабильные/подозрительные даты)."""
