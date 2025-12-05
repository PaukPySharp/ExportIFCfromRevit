# -*- coding: utf-8 -*-
"""Корзины логов для оркестратора и pyRevit-скриптов.

Назначение:
    - Дать унифицированный API для накопления строк-предупреждений/ошибок
      и последующей записи в текстовые логи.

Контракты:
    - Запись выполняется через utils.logs.write_log_lines().
    - Имена файлов логов согласованы с константами config.constants:
        * Оркестратор (tasks):
            - LOGFILE_VERSION_NOT_FOUND
            - LOGFILE_VERSION_TOO_NEW
        * pyRevit-скрипт (экспорт IFC):
            - LOGFILE_OPENING_ERRORS
            - LOGFILE_EXPORT_ERRORS
    - Имя LOGFILE_MISSING_VIEW (лог моделей без 3D-вида с именем из
      настроек [Revit] export_view3d_name) вычисляется из шаблона
      LOGFILE_MISSING_VIEW_TEMPLATE через
      utils.files.format_log_name_with_view().

Особенности:
    - Модуль может выполняться под IronPython 3.4 (pyRevit).
    - Допускается использование модуля typing для аннотаций типов, но без
      современного синтаксиса, требующего более новых версий Python
      (list[str], X | Y и т.п.) в исполняемом коде.
"""
from pathlib import Path

from config.constants import (
    LOGFILE_EXPORT_ERRORS,
    LOGFILE_OPENING_ERRORS,
    LOGFILE_VERSION_TOO_NEW,
    LOGFILE_VERSION_NOT_FOUND,
)

from utils.logs import write_log_lines
from utils.files import format_log_name_with_view

# Имя лог-файла моделей без 3D-вида для экспорта IFC
# (шаблон + имя вида из настроек [Revit] export_view3d_name).
LOGFILE_MISSING_VIEW = format_log_name_with_view()


class TasksLogBucket(object):
    """Корзина логов для этапа оркестрации (формирование задач/CSV).

    Поля:
        version_not_found: кейсы, где не определилась версия Revit.
        version_too_new:   кейсы, где версия выше поддерживаемого диапазона.
    """

    __slots__ = ("version_not_found", "version_too_new")

    def __init__(self) -> None:
        """Создаёт пустую корзину логов задач.

        Инициализирует списки:
            - version_not_found;
            - version_too_new.
        """
        # Список строк с моделями, для которых не удалось определить версию.
        self.version_not_found = []
        # Список строк с моделями, у которых версия выше поддерживаемого
        # диапазона (слишком новый Revit).
        self.version_too_new = []

    def write_logs(self, log_dir: Path) -> None:
        """Записывает накопленные кейсы в датированные файлы логов.

        :param log_dir: Директория, в которую будут записаны txt-логи.
        """
        if self.version_not_found:
            # sorted(...) — детерминированный вывод: порядок в логе
            # не зависит от порядка накопления сообщений.
            write_log_lines(
                log_dir,
                LOGFILE_VERSION_NOT_FOUND,
                sorted(self.version_not_found),
            )

        if self.version_too_new:
            # Та же идея: сортируем для предсказуемого порядка в логе.
            write_log_lines(
                log_dir,
                LOGFILE_VERSION_TOO_NEW,
                sorted(self.version_too_new),
            )


class PyRevitExportLogBucket(object):
    """Корзина логов для pyRevit-скрипта экспорта IFC.

    Поля:
        opening_errors:    модели, которые не открылись в Revit.
        missing_navisview: модели без 3D-вида с именем из настроек
                           ([Revit] export_view3d_name).
        export_errors:     модели, экспорт которых завершился с ошибкой.
    """

    __slots__ = ("opening_errors", "missing_navisview", "export_errors")

    def __init__(self) -> None:
        """Создаёт пустую корзину логов pyRevit-скрипта.

        Инициализирует списки:
            - opening_errors;
            - missing_navisview;
            - export_errors.
        """
        # Список строк с моделями, которые не удалось открыть в Revit.
        self.opening_errors = []
        # Список строк с моделями без 3D-вида с именем из настроек
        # (раздел [Revit], параметр export_view3d_name).
        self.missing_navisview = []
        # Список строк с моделями, экспорт которых завершился с ошибкой
        # (сбои внутри Revit API, doc.Export и т.п.).
        self.export_errors = []

    def write_logs(self, log_dir: Path) -> None:
        """Записывает накопленные кейсы в датированные файлы логов.

        Важно:
            - pyRevit-процесс может запускаться отдельно для каждой версии
              Revit, поэтому здесь мы только дописываем строки без
              разделителей; финальный разделитель на запуск оркестратора
              добавляется в ExportOrchestrator._finalize_pyrevit_logs().

        :param log_dir: Директория, в которую будут записаны txt-логи.
        """
        if self.opening_errors:
            # separator="" — не отбиваем блоки по каждой версии Revit;
            # разделитель добавляется один раз на запуск оркестратора.
            # sorted(...) — детерминированный порядок строк.
            write_log_lines(
                log_dir,
                LOGFILE_OPENING_ERRORS,
                sorted(self.opening_errors),
                separator="",
            )

        if self.missing_navisview:
            write_log_lines(
                log_dir,
                LOGFILE_MISSING_VIEW,
                sorted(self.missing_navisview),
                separator="",  # та же схема: блоки ставит оркестратор
            )

        if self.export_errors:
            write_log_lines(
                log_dir,
                LOGFILE_EXPORT_ERRORS,
                sorted(self.export_errors),
                separator="",  # отдельно фиксируем ошибки экспорта
            )
