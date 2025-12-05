# -*- coding: utf-8 -*-
"""Запуск pyRevit CLI для экспорта IFC.

Назначение:
    - Выполнить команду
      `pyrevit run <script> --models=Task<ver>.txt --revit=<ver> [--debug]`.

Контракты:
    - Путь к pyRevit-скрипту берётся из config.SCRIPT_EXPORT_IFC.
    - Путь к Task-файлу передаётся как есть, но конвертируется в «безопасный»
      через utils.cli.safe_path.
    - В дочерний процесс передаётся EXPORTIFC_ROOT=DIR_SCRIPTS, чтобы
      Settings мог корректно определить корень проекта.
    - Возвращает код возврата процесса: 0 — успех; иное — ошибка.

Особенности:
    - Используются «безопасные» пути (8.3/короткие) для скрипта и
      аргумента --models (минимизация проблем с пробелами/кириллицей).
    - Модуль не мутирует os.environ: формирует отдельный словарь env_add
      и передаёт его в run_cmd_streaming().
"""
import os
import logging
from pathlib import Path
from dataclasses import dataclass

from config import (
    LOGGER_NAME,
    DIR_SCRIPTS,
    SCRIPT_EXPORT_IFC
)

from utils.cli import run_cmd_streaming, safe_path

# Модульный логгер: наследует настройки от "export_ifc"
log = logging.getLogger(f"{LOGGER_NAME}.pyrevit_runner")


@dataclass(slots=True)
class PyRevitRunner:
    """Исполнитель вызовов pyRevit CLI.

    Параметры:
        script: Путь к скрипту ExportIFC.py, который будет запускаться
                через pyrevit run.
        debug:  Флаг отладочного режима (добавляет аргумент --debug).
    """

    # Путь к исполняемому скрипту pyRevit (ExportIFC.py)
    script: Path = SCRIPT_EXPORT_IFC
    # Флаг отладочного запуска (добавляет --debug к команде)
    debug: bool = False

    def __post_init__(self) -> None:
        """Нормализует путь к скрипту (safe_path + Path).

        На Windows safe_path может вернуть короткий 8.3-путь, чтобы
        pyRevit/Python корректно отработали даже с пробелами и Unicode.
        """
        self.script = Path(safe_path(self.script))

    # --------------------- публичный API ---------------------
    def run_for_version(self, version: int, task_file: Path) -> int:
        """Вызывает pyRevit CLI для указанной версии Revit.

        Команда имеет вид:
            pyrevit run <script> --models=Task<ver>.txt --revit=<ver> [--debug]

        Вывод pyRevit стримится построчно в логгер модуля (log.info).

        :param version:   Год/версия Revit (например, 2022).
        :param task_file: Путь к Task<version>.txt (список моделей).
        :return:          Код возврата процесса (0 — успех).
        """

        cmd = [
            "pyrevit",
            "run",
            str(self.script),
            "--models",
            safe_path(task_file),
            "--revit",
            str(version),
        ]
        if self.debug:
            cmd.append("--debug")

        # Важно:
        #   - on_line=log.info  -> каждая строка stdout pyRevit попадает в лог;
        #   - env_add           -> отдельный словарь окружения, не портим
        #                          глобальный os.environ.
        return run_cmd_streaming(
            cmd,
            on_line=log.info,
            env_add=self._build_env(),
        )

    # -------------------- внутренние методы --------------------
    @staticmethod
    def _build_env() -> dict[str, str]:
        """Формирует доп. окружение для процесса pyRevit.

        Добавляет корень скриптов проекта в PYTHONPATH/IRONPYTHONPATH и
        устанавливает EXPORTIFC_ROOT, чтобы Settings мог найти config/utils.

        :return: Словарь env_add для передачи в run_cmd_streaming().
        """
        # Корень с папками config/core/utils/revit/scripts.
        # Именно его Settings использует как main_dir/EXPORTIFC_ROOT.
        root = str(DIR_SCRIPTS)

        def _merge(var: str) -> str:
            """Возвращает PATH-подобную переменную с добавленным
               префиксом root.

            :param var: Имя переменной окружения (например, "PYTHONPATH"
                        или "IRONPYTHONPATH"), значение которой нужно
                        дополнить.
            :return: Новое значение переменной окружения с добавленным
                    в начало путём root. Если переменная была пуста,
                    возвращается только root.
            """
            prev = os.environ.get(var, "")
            return root if not prev else f"{root}{os.pathsep}{prev}"

        return {
            # Для Settings._detect_project_root() и всего,
            # что ищет EXPORTIFC_ROOT.
            "EXPORTIFC_ROOT": root,
            # Для обычного Python-импорта модулей проекта.
            "PYTHONPATH": _merge("PYTHONPATH"),
            # Для ironPython внутри pyRevit (видит тот же код проекта).
            "IRONPYTHONPATH": _merge("IRONPYTHONPATH"),
        }


# можно добавить «щадящую» проверку перед вызовами:
#
# # core/pyRevit_runner.py (псевдокод перед запуском версии)
# def _ensure_version_available(ver: int) -> bool:
#     # вариант 1: спросить `pyrevit cli list` (если доступно);
#     # вариант 2: проверить стандартные пути установки Revit
#     #            (Win registry / Program Files).
#     # Детали опущены — идея оставлена как возможное улучшение.
#     return True
#
# if not _ensure_version_available(version):
#     # здесь можно было бы записать информацию в отдельный bucket
#     # (например, TasksLogBucket) и пропустить запуск pyRevit
#     # для недоступной версии.
#     bucket.add_unavailable_version(version)
#     return False
