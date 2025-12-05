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
        * DEBUG      — добавляет флаг отладки к запуску pyRevit и включает
                       подробный консольный лог (уровень DEBUG);
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

    Поведение:
        - Настраивает консольный логгер: DEBUG включает подробный вывод.
        - Логирует старт/финиш прогона с фиксацией ключевых флагов.
        - В случае файловых ошибок выводит краткое сообщение и, при DEBUG,
          трассировку исключения через стандартный logging.

    Возвращает:
        0 — оркестратор завершился без жёстких ошибок;
        1 — были ошибки запуска pyRevit, сохранения history.xlsx или
            фатальная ошибка валидации файлов.
    """

    root_log = logging.getLogger(LOGGER_NAME)

    # 1. Настраиваем консольный логгер для корневого логгера приложения.
    level = logging.DEBUG if DEBUG else logging.INFO
    setup_console_logging(root_log, level=level)

    # 2. Логируем старт — отдельная метка, чтобы в логах было проще
    # находить границы одного запуска оркестратора.
    root_log.info(
        "[START] Запуск выгрузки IFC (debug=%s, run_pyrevit=%s)",
        DEBUG,
        RUN_PYREVIT,
    )

    # 3. Инициализируем и запускаем оркестратор экспорта.
    success = _run_orchestration(root_log)

    # 4. Финальный лог — симметричная метка к [START] с учётом статуса.
    if success:
        root_log.info("[FINISH] Выгрузка IFC завершена успешно")
        return 0
    else:
        root_log.error("[FINISH] Выгрузка IFC завершена с ошибками")
        return 1


# ------------------------- вспомогательные функции -------------------------
def _log_fatal_file_error(log: logging.Logger, exc: Exception) -> None:
    """Выводит фатальную ошибку валидации файлов в лог.

    Поведение:
        - Пишет краткое сообщение уровня CRITICAL для пользователя.
        - Стек исключения выводится только на уровне DEBUG, чтобы не
          засорять типовой консольный вывод.
        - Исключение не пробрасывается дальше: вызывающий код решает,
          как завершать выполнение.

    :param log: Корневой логгер приложения.
    :param exc: Перехваченное файловое исключение (FileNotFoundError,
                NotADirectoryError и т.п.).
    """

    log.critical("Фатальная ошибка валидации файлов: %s", exc)
    # Если включён DEBUG, печатаем трассировку стандартными средствами logging.
    if log.isEnabledFor(logging.DEBUG):
        log.debug("Детали исключения", exc_info=True)


def _run_orchestration(log: logging.Logger) -> bool | None:
    """Создаёт и запускает оркестратор с защитой от файловых ошибок.

    Результаты:
        - True   — оркестратор отработал без жёстких ошибок.
        - False  — запуск завершился, но сообщил об ошибках.
        - None   — инициализация или работа прервалась из-за проблем с
                   валидностью входных путей или файлов (исключения
                   FileNotFoundError / NotADirectoryError перехватываются
                   и логируются без повторного выброса).

    :param log: Корневой логгер приложения.
    :return: Булев статус успеха или None при FileNotFoundError /
             NotADirectoryError.
    """

    try:
        orchestrator = ExportOrchestrator(DEBUG, RUN_PYREVIT)
        return orchestrator.run()
    except (FileNotFoundError, NotADirectoryError) as exc:
        _log_fatal_file_error(log, exc)
        return None


# -------------------------------- bootstrap --------------------------------
if __name__ == "__main__":
    raise SystemExit(main())
