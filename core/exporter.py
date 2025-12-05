# -*- coding: utf-8 -*-
"""Оркестрация экспорта IFC из Revit через pyRevit.

Назначение:
    - Загрузка конфигурации моделей (<MANAGE_NAME>.xlsx).
    - Проверка актуальности (история + файлы IFC на диске).
    - Группировка моделей по версиям Revit и формирование Task<ver>.txt.
    - Подготовка временного CSV (<TMP_NAME>.csv) для каждой версии.
    - Запуск pyRevit CLI по версиям и запись логов проблемных кейсов.

Контракты:
    - Сравнение дат файлов RVT/IFC «до минут».
    - Версии Revit берутся из канонического списка REVIT_VERSIONS.
    - Пути к Task-файлам формируются через config.build_task_path(version).
    - История (<HISTORY_NAME>.xlsx) всегда сохраняется по итогам прогона
      (даже если часть версий завершилась с ошибкой или включён dry-run).
    - <TMP_NAME>.csv удаляется только при успешном запуске соответствующей
      версии.

Особенности:
    - run_pyrevit=False (dry-run):
        * формируем Task/CSV по всем версиям;
        * pyRevit фактически не запускается;
        * <HISTORY_NAME>.xlsx всё равно обновляется (отражает факт проверки
        моделей программой, а не гарантированно успешного экспорта IFC).
"""
import logging
from datetime import datetime
from typing import List, Optional

from config import (
    DIR_LOGS,
    LOGGER_NAME,
    MANAGE_NAME,
    HISTORY_NAME,
    DIR_ADMIN_DATA,
    build_task_path,
)
from config.constants import (
    LOGFILE_MTIME_ISSUES,
    LOGFILE_EXPORT_ERRORS,
    LOGFILE_OPENING_ERRORS,
)

from core.models import RevitModel
from core.manage import ManageDataLoader
from core.history import HistoryManager
from core.ifc_checker import IFCChecker
from core.tasks import ExportTaskManager
from core.pyRevit_runner import PyRevitRunner

from utils.fs import ensure_dir
from utils.files import format_log_name_with_view
from utils.logs import write_log_lines, append_log_separator


# Модульный логгер: наследует настройки от "export_ifc"
log = logging.getLogger(f"{LOGGER_NAME}.exporter")

# Имя лог-файла моделей без 3D-вида для экспорта IFC
# (шаблон + имя вида из настроек [Revit] export_view3d_name).
LOGFILE_MISSING_VIEW = format_log_name_with_view()


class ExportOrchestrator:
    """Фасадная точка запуска экспорта IFC.

    Состояние:
        - manage   — загрузчик данных из <MANAGE_NAME>.xlsx;
        - history  — менеджер истории выгрузок (<HISTORY_NAME>.xlsx);
        - ifc      — проверка актуальности целевых IFC на диске;
        - taskman  — группировка моделей по версиям и генерация артефактов;
        - runner   — исполнитель вызовов pyRevit (CLI).

    Методы:
        - run() — выполняет полный цикл экспорта.
    """

    def __init__(self, debug: bool, run_pyrevit: bool) -> None:
        """Инициализация компонентов без тяжёлых побочных эффектов.

        :param debug: Флаг отладки для PyRevitRunner
                      (добавляет --debug к CLI).
        :param run_pyrevit: Управляет фактическим запуском pyRevit:
            * True  — выполнить pyRevit для каждой версии;
            * False — dry-run, сформировать Task/CSV без запуска CLI.
        """
        # Флаг режима запуска pyRevit (dry-run / normal)
        self.run_pyrevit: bool = run_pyrevit

        # Загрузчик <MANAGE_NAME>.xlsx → модели и ignore-set
        self.manage: ManageDataLoader = ManageDataLoader()

        # История выгрузок IFC (<HISTORY_NAME>.xlsx)
        self.history: HistoryManager = HistoryManager()

        # Проверка актуальности целевых IFC на диске
        self.ifc: IFCChecker = IFCChecker()

        # Менеджер задач экспорта (группировка по версиям, Task/CSV,
        # bucket-логи)
        self.taskman: ExportTaskManager = ExportTaskManager()

        # Обёртка над запуском pyRevit CLI
        self.runner: PyRevitRunner = PyRevitRunner(debug=debug)

        # Отметка начала текущего запуска (для пост-обработки логов)
        self._run_started_at: Optional[datetime] = None

    # ----------------------------- публичный API -----------------------------
    def run(self) -> bool:
        """
        Запускает полный цикл экспорта IFC для всех моделей из
        <MANAGE_NAME>.xlsx.

        Этапы:
            1. Чтение моделей и фильтрация по ignore-листу.
            2. Гарантия наличия папки для логов и артефактов.
            3. Запись предупреждений по проблемным mtime (если есть).
            4. Решение, какие модели требуют экспорта (history + IFCChecker).
            5. Группировка моделей по версиям Revit и формирование
               Task<ver>.txt.
            6. Подготовка <TMP_NAME>.csv и запуск pyRevit по версиям
               (или dry-run).
            7. Сохранение <HISTORY_NAME>.xlsx и финализация txt-логов pyRevit.

        Особенности:
            - Ошибки открытия/экспорта отдельных моделей не прерывают цикл:
              они логируются и попадают в txt-отчёты.
            - История (<HISTORY_NAME>.xlsx) сохраняется всегда, даже если
              часть версий Revit завершилась с ошибкой или включён dry-run.

        Возвращает:
            True  — ни одна версия Revit не завершилась с ошибкой
                    (или pyRevit не запускался) и history.xlsx
                    удалось сохранить;
            False — были ошибки запуска pyRevit хотя бы для одной версии
                    и/или не удалось сохранить history.xlsx.
        """
        # фиксируем время начала выполнения программы — нужно, чтобы
        # разделитель в txt-логах добавлялся только при их изменении
        # в текущем запуске
        self._run_started_at = datetime.now()

        # 1. Загрузка моделей и применение ignore-листа
        models = self._get_filtered_models()

        # 2. Гарантируем папку под артефакты
        self._ensure_logs_dir()

        # 3. Предупреждения по mtime моделей (если были проблемы).
        #    Лог LOGFILE_MTIME_ISSUES пишется сразу, без участия
        #    ExportTaskManager.
        self._log_mtime_issues()

        # 4. Решение о необходимости экспорта и наполнение taskman.
        self._collect_export_tasks(models)

        # 5. Формирование Task-файлов.
        #    Task<ver>.txt по всем собранным версиям, порядок внутри не важен.
        self.taskman.write_task_files()

        # Лог-сводка по версиям.
        self._log_tasks_summary()

        # 6. Запуск pyRevit по версиям (или dry-run).
        any_failures = self._run_pyrevit_for_versions()

        # 7. Сохранение истории.
        # Историю выгрузок сохраняем всегда (в том числе при dry-run):
        #   - history фиксирует факт "последней проверки/подготовки экспорта";
        #   - актуальность IFC при последующих запусках ВСЕГДА проверяется
        #     по реальным файлам (IFCChecker) и не опирается только на history.
        history_saved = True
        try:
            self.history.save()
        except Exception as exc:
            history_saved = False
            log.error(
                "Не удалось сохранить %s.xlsx: %s",
                HISTORY_NAME,
                exc,
                exc_info=True,
            )

        if any_failures and self.run_pyrevit:
            if history_saved:
                log.warning(
                    "История выгрузок сохранена, но некоторые версии "
                    "Revit завершились с ошибкой. "
                    "Актуальность IFC при последующих запусках будет "
                    "всегда перепроверяться по файлам."
                )
            else:
                log.warning(
                    "Некоторые версии Revit завершились с ошибкой, "
                    "к тому же не удалось сохранить %s.xlsx. "
                    "Актуальность IFC при последующих запусках всё равно "
                    "будет перепроверяться по файлам.",
                    HISTORY_NAME,
                )

        # 8. Завершение логов pyRevit (если они есть):
        #    добавляем один разделитель на запуск оркестратора для логов
        #    ошибок открытия моделей, отсутствующих 3D-видов и ошибок экспорта.
        if self.run_pyrevit:
            self._finalize_pyrevit_logs()

        # 9. Запись txt-логов задач по версиям моделей.
        #    Это сводные логи ExportTaskManager.logs, собранные на основе
        #    данных <MANAGE_NAME>.xlsx:
        #      - модели с нераспознанной версией Revit;
        #      - модели с версией выше поддерживаемого диапазона.
        self.taskman.logs.write_logs(DIR_LOGS)
        log.info("TXT-логи задач записаны в каталог: %s", DIR_LOGS)

        # 10. Итоговый статус для внешнего кода (main.py).
        success = (not any_failures) and history_saved

        if success:
            log.info(
                "Оркестратор экспорта завершён без жёстких ошибок "
                "(any_failures=%s, history_saved=%s).",
                any_failures,
                history_saved,
            )
        else:
            log.error(
                "Оркестратор экспорта завершён с ошибками "
                "(any_failures=%s, history_saved=%s).",
                any_failures,
                history_saved,
            )

        return success

    # --------------------------- внутренние методы ---------------------------
    def _get_filtered_models(self) -> List[RevitModel]:
        """Возвращает список моделей после применения ignore-листа.

        Назначение:
            - скопировать manage.models;
            - отфильтровать по self.manage.ignore;
            - залогировать исходное и итоговое количество моделей.

        :return: Список экземпляров RevitModel.
        """
        models_source = self.manage.models
        ignore_set = self.manage.ignore

        log.info(
            "Загружено моделей из %s.xlsx: %d (ignore: %d)",
            MANAGE_NAME,
            len(models_source),
            len(ignore_set),
        )

        # Нет ignore-листа — возвращаем копию исходного списка.
        if not ignore_set:
            models = list(models_source)
            log.info("Моделей после применения ignore-листа: %d", len(models))
            return models

        # Фильтрация по ignore: в manage.ignore хранятся строковые пути,
        # поэтому приводим rvt_path к str.
        models = [
            m for m in models_source
            if str(m.rvt_path) not in ignore_set
        ]

        log.info("Моделей после применения ignore-листа: %d", len(models))
        return models

    def _ensure_logs_dir(self) -> None:
        """Гарантирует наличие каталога для логов и служебных файлов."""
        # Папка логов нужна для:
        #   - txt-отчётов ExportTaskManager.logs,
        #   - возможных служебных файлов (mtime-issues и пр.).
        ensure_dir(DIR_LOGS)

    def _log_mtime_issues(self) -> None:
        """Фиксирует проблемы с mtime моделей в отдельном txt-логе (если есть).

        Если список self.manage.models_mtime пуст, ничего не делает.
        """
        # Если при чтении <MANAGE_NAME>.xlsx были проблемы с датами модификации
        # (отсутствует файл, нет прав, некорректный путь и т.п.) —
        # фиксируем это отдельным txt-логом.
        if not self.manage.models_mtime:
            return

        # Детерминированный вывод: убираем дубликаты и сортируем.
        lines = sorted(set(self.manage.models_mtime))
        write_log_lines(DIR_LOGS, LOGFILE_MTIME_ISSUES, lines)

        log.warning(
            "Обнаружены проблемы с mtime у %d моделей "
            "(подробности в %s*.txt)",
            len(lines),
            LOGFILE_MTIME_ISSUES,
        )

    def _collect_export_tasks(self, models: List[RevitModel]) -> None:
        """Определяет, какие модели требуют экспорта, и группирует их
        по версиям.

        Назначение:
            - вызвать RevitModel.needs_export(history, ifc) для каждой модели;
            - отфильтровать модели, для которых экспорт не требуется;
            - для остальных:
                * определить версию Revit;
                * добавить модель в ExportTaskManager;
                * обновить историю (только для распознанных версий).

        :param models: Список экземпляров RevitModel.
        """

        # Счётчик моделей, которым действительно требуется экспорт / проверка.
        to_export = 0

        for model in models:
            # Нужен ли экспорт?
            #     Логика внутри model.needs_export():
            #       - history       → не менялся ли RVT с момента последнего
            #                         рассмотрения;
            #       - IFCChecker    → существуют ли актуальные IFC
            #                         (mapped/nomap).
            #     Если оба IFC свежие и история совпадает, модель пропускается.
            if not model.needs_export(self.history, self.ifc):
                continue

            to_export += 1

            # Определяем версию Revit (читает build из RVT и маппит в год).
            model.load_version()
            ver = model.version

            # Группируем модель по версии Revit. Внутри add_model уже
            # есть обработка аномалий (непонятная/неподдерживаемая версия).
            self.taskman.add_model(model, ver)

            # История фиксируется только для распознанных версий:
            # если версия не определена, модель не попадает в history.
            if ver is not None:
                self.history.update_record(model)

        log.info("Моделей, требующих проверки/экспорта: %d", to_export)

    def _log_tasks_summary(self) -> None:
        """Логирует сводку по версиям Revit и количеству моделей в заданиях."""

        # Для информативности логируем, сколько моделей пришлось на
        # каждую версию.
        if self.taskman.tasks:
            for ver in sorted(self.taskman.tasks.keys()):
                bucket = self.taskman.tasks[ver]
                log.info(
                    "Версия Revit %s: моделей в задании: %d",
                    ver,
                    len(bucket),
                )
        else:
            log.info("Нет моделей, требующих экспорта: Task-файлы пусты.")

    def _run_pyrevit_for_versions(self) -> bool:
        """Запускает pyRevit по версиям (или имитирует запуск в dry-run).

        :return: True, если хотя бы одна версия завершилась с ошибкой.
        """
        # Если задач нет — сюда мы пришли уже после _log_tasks_summary(),
        # который всё залогировал. Просто выходим.
        if not self.taskman.tasks:
            return False

        # Флаг, что хотя бы для одной версии pyRevit завершился с ошибкой.
        any_failures = False

        # Обрабатываем версии детерминированно (по возрастанию).
        for ver in sorted(self.taskman.tasks.keys()):
            # Путь к Task-файлу для данной версии.
            task_file = build_task_path(ver)
            # Временный CSV с заданиями по данной версии (один <TMP_NAME>.csv
            # на версию).
            tmp_csv = self.taskman.write_tmp_csv(DIR_ADMIN_DATA, ver)

            if not self.run_pyrevit:
                # Dry-run: создаём Task и <TMP_NAME>.csv, но не запускаем
                # pyRevit.
                # Это удобно для отладки состава заданий и CSV.
                log.info(
                    "[DRY-RUN] pyRevit для Revit %s не запускается "
                    "(task=%s, csv=%s)",
                    ver,
                    task_file,
                    tmp_csv,
                )
                # <TMP_NAME>.csv осознанно сохраняем для анализа.
                continue

            log.info(
                "Запуск pyRevit для Revit %s (task=%s)",
                ver,
                task_file.name,
            )

            # rc — код возврата pyRevit CLI:
            #   0   → условный успех;
            #  !=0  → что-то пошло не так (код зависит от скрипта/pyRevit).
            rc = self.runner.run_for_version(ver, task_file)

            if rc != 0:
                any_failures = True
                log.error(
                    "pyRevit для Revit %s завершился с ошибкой (код %s); "
                    "файл %s сохранён для анализа",
                    ver,
                    rc,
                    tmp_csv.name,
                )
                # <TMP_NAME>.csv оставляем на диске для разбора.
            else:
                tmp_csv.unlink(missing_ok=True)
                log.info(
                    "pyRevit для Revit %s завершился успешно, файл %s удалён",
                    ver,
                    tmp_csv.name,
                )

        return any_failures

    def _finalize_pyrevit_logs(self) -> None:
        """Добивает разделители в логи pyRevit за этот запуск.

        Делает один визуальный блок на запуск оркестратора, даже если
        внутри было несколько версий Revit. Разделитель ставится только
        для логов, которые были затронуты в текущем запуске (по mtime).
        """

        # Логи 1_/2_/5_* формируются в PyRevitExportLogBucket внутри
        # pyRevit-скрипта:
        #   - для каждой версии Revit запускается отдельный процесс;
        #   - в файлы логов дописываются только строки, без разделителей.
        #
        # На уровне оркестратора доводим формат до «1 запуск = 1 блок»:
        # для уже существующих файлов добавляем в конец строку-разделитель.

        # started_at фиксируется при запуске, чтобы не трогать логи,
        # которые не менялись в текущем прогоне
        # (фильтр по mtime в append_log_separator).
        started_at = (
            self._run_started_at.timestamp() if self._run_started_at else None
        )

        for base_name in (
            LOGFILE_OPENING_ERRORS,
            LOGFILE_MISSING_VIEW,
            LOGFILE_EXPORT_ERRORS,
        ):
            append_log_separator(
                DIR_LOGS,
                base_name,
                min_mtime=started_at,
            )
