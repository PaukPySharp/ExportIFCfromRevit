# -*- coding: utf-8 -*-
"""Выгрузка IFC из Revit (pyRevit).

Назначение:
    - Запуск под pyRevit для пакетного экспорта IFC по списку моделей,
      подготовленному внешним оркестратором в admin_data/<TMP_NAME>.csv.
    - Выполнение экспорта в один или два направления: с маппингом и без.

Контракты:
    - Внешний CPython-оркестратор формирует файл admin_data/<TMP_NAME>.csv.
    - В <TMP_NAME>.csv каждая строка соответствует одной модели и содержит
      6 колонок (разделитель ';', без заголовка):
        0. rvt_path              -> путь к файлу *.rvt
        1. output_dir_mapping    -> каталог выгрузки с маппингом
        2. mapping_json          -> JSON настроек IFC-экспорта (с маппингом)
        3. family_mapping_file   -> файл маппинга семейств
        4. output_dir_nomap      -> каталог выгрузки без маппинга (опционально)
        5. nomap_json            -> JSON настроек IFC-экспорта без маппинга
                                    (опционально).
    - Порядок строк в <TMP_NAME>.csv определяет порядок экспорта.
    - Глобальная __models__ из pyRevit не используется как основной
      источник путей; при необходимости может быть задействована
      отдельным отладочным кодом.

Особенности:
    - Модуль может выполняться под IronPython 3.4 (pyRevit).
    - Допускается использование модуля typing для аннотаций типов, но без
      современного синтаксиса, требующего более новых версий Python
      (list[str], X | Y и т.п.) в исполняемом коде.
    - Документы открываются через HOST_APP.app.OpenDocumentFile с
      безопасными опциями:
        DetachFromCentral, OpenAllWorksets, AllowOpeningLocalByWrongUser,
        IgnoreExtensibleStorageSchemaConflict.
    - Любые изменения в документе откатываются: транзакция RollBack
      (экспорт не влияет на исходную модель).
    - Логирование проблем по моделям (ошибки открытия, отсутствие 3D-вида,
      ошибки экспорта) ведётся через
      utils.log_buckets.PyRevitExportLogBucket →
      utils.logs.write_log_lines.
    - FLAG_UNMAPPED управляет сценарием «без маппинга».
"""
import gc
from pathlib import Path
from typing import Union, Optional

# доступ к Revit-хосту внутри pyRevit
from pyrevit import HOST_APP  # type: ignore

from config.settings import SETTINGS as STG
from config.paths import DIR_ADMIN_DATA, DIR_LOGS

from revit._api import DB
from revit.jobs import ExportJob
from revit.task_reader import iter_jobs
from revit.views import find_export_view3d
from revit.ifc_options import load_mapping_json, build_ifc_export_options

from utils.log_buckets import PyRevitExportLogBucket as LogBucket

FLAG_UNMAPPED = STG.enable_unmapped_export


# --------------------- основной исполнитель скрипта ---------------------
class ExportIFCRunner(object):
    """Исполнитель экспорта IFC под pyRevit.

    Назначение:
        - Для каждой строки в admin_data/<TMP_NAME>.csv:
            * открыть модель,
            * найти 3D-вид,
            * выполнить экспорт(ы),
            * откатить транзакцию.

    Контракты:
        - <TMP_NAME>.csv подготовлен внешним оркестратором и содержит
          корректные пути.
        - __models__ может присутствовать в окружении pyRevit, но
          не используется как источник путей (при необходимости —
          только для отладки).

    Особенности:
        - Открытие через HOST_APP (корректно внутри pyRevit).
        - Сборщики мусора: Python (gc.collect) +
          Revit API (PurgeReleasedAPIObjects).
    """

    __slots__ = ("_admin_dir", "_log_dir", "_logs")

    def __init__(self, admin_dir: Path, log_dir: Path) -> None:
        """Создаёт исполнитель экспорта IFC.

        :param admin_dir: Путь к каталогу admin_data.
        :param log_dir:   Путь к каталогу логов.
        """
        self._admin_dir = admin_dir
        self._log_dir = log_dir
        self._logs = LogBucket()

    # --------------------- фабрика опций открытия -------------------------
    @staticmethod
    def _build_open_options() -> DB.OpenOptions:
        """Создаёт и настраивает OpenOptions для пакетного открытия моделей.

        Назначение:
            - Сконфигурировать безопасные и «тихие» параметры открытия,
              чтобы ускорить пакетную обработку и исключить побочные изменения.

        Контракты:
            - Все рабочие наборы открываются (OpenAllWorksets).
            - Модель отсоединяется от центральной с сохранением рабочих
              наборов.
            - Разрешено открытие локального файла от другого пользователя.
            - Игнорируется конфликт схем расширяемого хранилища.
            - Иностранные элементы разрешено открывать.

        Особенности:
            - Метод вынесен отдельно, чтобы редактировать все опции в одном
              месте.
        """
        opts = DB.OpenOptions()
        # Отсоединяем от центральной с сохранением рабочих наборов
        opts.DetachFromCentralOption = (
            DB.DetachFromCentralOption.DetachAndPreserveWorksets
        )
        # Разрешаем открытие локального файла «не тем» пользователем
        opts.AllowOpeningLocalByWrongUser = True
        # Игнорируем конфликт схем Extensible Storage
        opts.IgnoreExtensibleStorageSchemaConflict = True
        # Разрешаем открытие «иностранных» элементов (связанные файлы и т.п.)
        opts.OpenForeignOption = DB.OpenForeignOption.Open
        # Открываем все рабочие наборы — актуальный вариант для
        # полного экспорта.
        ws_cfg = DB.WorksetConfiguration(
            DB.WorksetConfigurationOption.OpenAllWorksets
        )
        opts.SetOpenWorksetsConfiguration(ws_cfg)
        return opts

    # ---------------- открытие и закрытие документа -----------------------
    def _open_doc(self, rvt_path: Union[Path, str]) -> Optional[DB.Document]:
        """Открывает документ Revit с безопасными опциями.

        В обычной ситуации возвращает открытый документ. При проблемах
        может быть выброшено исключение; на некоторых конфигурациях возможен
        редкий сценарий, когда Revit возвращает None без исключения —
        это обрабатывается в вызывающем коде как ошибка открытия.

        :param rvt_path: Пользовательский путь к файлу *.rvt (str или Path).
        :return:         Открытый документ Revit или None.
        """
        # Переводим обычный путь в понятный Revit API формат ModelPath
        model_path = DB.ModelPathUtils.ConvertUserVisiblePathToModelPath(
            str(rvt_path)
        )
        # Опции открытия — собраны в отдельном методе
        opts = self._build_open_options()
        # Открываем через HOST_APP.app — корректно внутри pyRevit
        return HOST_APP.app.OpenDocumentFile(model_path, opts)

    @staticmethod
    def _close_doc_safely(doc: DB.Document) -> None:
        """Закрывает документ, очищает ресурсы Python и Revit API.

        :param doc: Открытый документ Revit.
        """
        try:
            doc.Close(False)
        finally:
            gc.collect()
            try:
                doc.Application.PurgeReleasedAPIObjects()
            except Exception:
                # На некоторых конфигурациях может бросать исключение —
                # не критично.
                pass

    # ------------------------ экспорт одной модели ------------------------
    def _export_one(self, doc: DB.Document, job: ExportJob) -> None:
        """Экспортирует IFC (с маппингом и без) для одной открытой модели.

        :param doc: Открытый документ Revit.
        :param job: Объект задания экспорта (см. revit.jobs.ExportJob).
        """
        # Ищем 3D-вид для экспорта согласно настройкам проекта
        view3d = find_export_view3d(doc)
        if view3d is None:
            self._logs.missing_navisview.append(
                f"{job.rvt_path} - в модели отсутствует 3D-вид для экспорта "
                f"({STG.export_view3d_name})"
            )
            return

        # Транзакция нужна только как «контейнер» для экспорта — затем откат
        t = DB.Transaction(doc, "ExportIFC")
        t.Start()  # type: ignore
        try:
            # получаем имя IFC-файла из пути к RVT
            ifc_name = job.rvt_path.stem

            # --- Экспорт с маппингом ---
            if job.output_dir_mapping and job.mapping_json:
                self._export_with_config(
                    doc,
                    view3d,
                    ifc_name,
                    job.output_dir_mapping,
                    job.mapping_json,
                    job.family_mapping_file,
                )

            # --- Экспорт без маппинга (если задан) ---
            if FLAG_UNMAPPED and job.output_dir_nomap and job.nomap_json:
                self._export_with_config(
                    doc,
                    view3d,
                    ifc_name,
                    job.output_dir_nomap,
                    job.nomap_json,
                    job.family_mapping_file,
                )
        finally:
            # Вне зависимости от результата экспорта откатываем транзакцию,
            # чтобы не засорять историю изменений документа.
            t.RollBack()  # type: ignore

    # ---------------- экспорт по одному набору настроек -----------------
    def _export_with_config(
        self,
        doc: DB.Document,
        view3d: DB.View,
        ifc_name: str,
        output_dir: Path,
        config_json: Path,
        family_mapping_file: Path,
    ) -> None:
        """Выполняет один экспорт IFC по указанному набору настроек.

        Назначение:
            - Общая часть для сценариев «с маппингом» и «без маппинга»;

        Поведение:
            - читает JSON-конфиг экспорта;
            - строит IFCExportOptions;
            - вызывает doc.Export() в нужную директорию.

        :param doc: Открытый документ Revit.
        :param view3d: 3D-вид, с которого выполняется экспорт.
        :param ifc_name: Имя IFC-файла без расширения.
        :param output_dir: Целевая директория выгрузки IFC.
        :param config_json: JSON-файл настроек экспорта IFC.
        :param family_mapping_file: Файл маппинга семейств/категорий.
        """
        # получаем опции экспорта в .NET-словарь
        cfg = load_mapping_json(str(config_json))

        # строим опции экспорта IFC
        ifc_opts = build_ifc_export_options(
            str(family_mapping_file),
            cfg,
            view3d.Id,
        )

        # экспортируем IFC с опциями в заданную директорию
        doc.Export(
            str(output_dir),
            ifc_name,
            ifc_opts,
        )

    # --------------------------- основной цикл -----------------------------
    def run(self) -> None:
        """
        Основной цикл обработки всех заданий из admin_data/<TMP_NAME>.csv.
        """
        jobs = iter_jobs(self._admin_dir)
        if not jobs:
            return

        for job in jobs:
            # 0) Быстрая проверка: файл модели должен существовать на диске.
            rvt_path = job.rvt_path  # ExportJob уже приводит к Path
            if not rvt_path.exists():
                self._logs.opening_errors.append(
                    f"{rvt_path} - файл модели не найден на диске"
                )
                continue

            # 1) Открываем документ по пути из <TMP_NAME>.csv
            try:
                doc = self._open_doc(job.rvt_path)
            except Exception as e:
                # Любые сбои при открытии (ошибки ModelPath, лицензии,
                # конфликтов аддинов и т.п.) не должны ронять цикл:
                # фиксируем проблему в лог и двигаемся дальше.
                self._logs.opening_errors.append(
                    f"{job.rvt_path} - модель не открылась в Revit ({e})"
                )
                continue

            if doc is None:
                # На всякий случай обрабатываем аномальный сценарий,
                # когда OpenDocumentFile возвращает None без исключения.
                self._logs.opening_errors.append(
                    f"{job.rvt_path} - модель не открылась в Revit "
                    f"(OpenDocumentFile вернул None)"
                )
                continue

            # 2) Экспорт IFC (с последующим откатом)
            try:
                self._export_one(doc, job)
            except Exception as e:
                # Любые сбои при экспорте (ошибки Revit API, doc.Export и т.п.)
                # не должны прерывать общий цикл: фиксируем проблему и
                # идём дальше.
                self._logs.export_errors.append(
                    f"{job.rvt_path} - ошибка экспорта: {e}"
                )
            finally:
                self._close_doc_safely(doc)

        # 3) Записываем накопленные логи в файлы
        self._logs.write_logs(self._log_dir)


# ------------------------ точка входа для pyRevit -------------------------
def main() -> None:
    """Точка входа для pyRevit.

    pyRevit исполняет модуль целиком, поэтому main() вызывается напрямую,
    без проверки __name__.
    """
    runner = ExportIFCRunner(DIR_ADMIN_DATA, DIR_LOGS)
    runner.run()


# pyRevit импортирует и исполняет модуль, поэтому main() вызывается всегда.
main()


# ------ DEPRECATED: старый вариант настройки открытия (для справки) ------
# ------ код из _build_open_options ------
# # Закрываем все рабочие наборы для ускорения открытия
# # (старый вариант, оставлен для справки).
# ws_cfg = DB.WorksetConfiguration(
#     DB.WorksetConfigurationOption.CloseAllWorksets
# )
