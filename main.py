# -*- coding: utf-8 -*-
"""Точка входа приложения ExportIFC.

Назначение:
    - Инициализация фасада оркестрации экспорта (ExportOrchestrator).
    - Запуск полного цикла выгрузки IFC из моделей Revit.

Контракты:
    - Перед запуском должны быть настроены settings.ini и <MANAGE_NAME>.xlsx.
    - Запуск производится из окружения CPython (не из-под Revit/pyRevit).
    - Все побочные эффекты (создание Task/CSV, изменение <HISTORY_NAME>.xlsx,
      запуск pyRevit-скрипта) инкапсулированы внутри ExportOrchestrator.

Особенности:
    - Модуль безопасно импортируется: при импорте ничего не запускается.
    - Поведение управляется двумя флагами DEBUG и RUN_PYREVIT ниже:
        * DEBUG      — добавляет флаг отладки к запуску pyRevit;
        * RUN_PYREVIT — при False выполняется dry-run без вызова pyRevit.
"""
import logging

from config import LOGGER_NAME

from core.exporter import ExportOrchestrator
from core.console_output import setup_console_logging

# -------------------------- настройки запуска ---------------------------
# Отладочный режим pyRevit (добавляет аргумент --debug к команде запуска).
DEBUG: bool = False

# Флаг запуска pyRevit:
#   True  — выполнять команды pyRevit;
#   False — dry-run: подготовка файлов (Task/CSV, <HISTORY_NAME>.xlsx)
#           без запуска pyRevit-скрипта.
RUN_PYREVIT: bool = True


# ------------------------------ публичный API ------------------------------
def main() -> int:
    """Запускает оркестрацию экспорта IFC.

    Возвращает:
        0 — оркестратор завершился без жёстких ошибок;
        1 — были ошибки запуска pyRevit и/или сохранения history.xlsx.
    """
    root_log = logging.getLogger(LOGGER_NAME)

    # 1. Настраиваем консольный логгер для корневого логгера приложения.
    setup_console_logging(root_log, level=logging.INFO)

    # 2. Логируем старт — отдельная метка, чтобы в логах было проще
    # находить границы одного запуска оркестратора.
    root_log.info(
        "[START] Запуск выгрузки IFC (debug=%s, run_pyrevit=%s)",
        DEBUG,
        RUN_PYREVIT,
    )

    # 3. Инициализируем и запускаем оркестратор экспорта.
    orchestrator = ExportOrchestrator(DEBUG, RUN_PYREVIT)
    success = orchestrator.run()

    # 4. Финальный лог — симметричная метка к [START] с учётом статуса.
    if success:
        root_log.info("[FINISH] Выгрузка IFC завершена успешно")
        return 0
    else:
        root_log.error("[FINISH] Выгрузка IFC завершена с ошибками")
        return 1


# -------------------------------- bootstrap --------------------------------
if __name__ == "__main__":
    raise SystemExit(main())
