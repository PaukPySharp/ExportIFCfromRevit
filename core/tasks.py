# -*- coding: utf-8 -*-
"""Формирование задач экспорта и вспомогательных файлов.

Назначение:
    - Группировка моделей по версиям Revit.
    - Генерация файлов задач Task<версия>.txt.
    - Подготовка временного CSV (<TMP_NAME>.csv) для скрипта экспорта.

Контракты:
    - Список поддерживаемых версий берётся из REVIT_VERSIONS (config).
    - Пути к Task-файлам формируются через build_task_path(version).
    - Путь к временным CSV формируется через build_csv_path().
    - Экземпляр ExportTaskManager не пишет в лог напрямую, а заполняет
      TasksLogBucket; запись в лог выполняется снаружи (ExportOrchestrator).
    - Модуль не решает, нужна ли выгрузка модели — он работает только
      с уже отфильтрованными моделями.

Особенности:
    - Порядок версий и моделей детерминирован:
        * версии обрабатываются по возрастанию;
        * модели внутри версии сортируются по str(rvt_path).

Правила распределения версий:
    - version is None → запись кейса в лог «версия не найдена».
    - version < _min_supported → используется _min_supported.
    - _min_supported ≤ version ≤ _max_supported → используется
      указанная версия.
    - version > _max_supported → запись кейса в лог
      «версия выше поддерживаемых».
"""
from csv import writer
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from config import (
    REVIT_VERSIONS,
    build_task_path,
    build_csv_path,
)

from core.models import RevitModel

from utils.log_buckets import TasksLogBucket as LogBucket

# Удобный псевдоним для пар (модель, версия).
ModelVersionPair = tuple[RevitModel, Optional[int]]


@dataclass(slots=True)
class ExportTaskManager:
    """Группировка моделей по версиям Revit и формирование файлов задач/CSV.

    Состояние:
        tasks:              Корзины моделей по версиям Revit.
        logs:               Агрегатор проблемных кейсов (TasksLogBucket).
        _min_supported:     Минимальная поддерживаемая версия Revit.
        _max_supported:     Максимальная поддерживаемая версия Revit.
        _supported_versions: Канонический отсортированный список
                            поддерживаемых версий (из config.REVIT_VERSIONS).
    """

    # Корзины моделей по версиям Revit.
    tasks: Dict[int, List[RevitModel]] = field(default_factory=dict)

    # Агрегатор сообщений о проблемных моделях.
    logs: LogBucket = field(default_factory=LogBucket)

    _min_supported: int = field(init=False)
    _max_supported: int = field(init=False)

    # Неизменяемая фиксация канонического списка версий
    # (защита от случайной мутации).
    _supported_versions: tuple[int, ...] = tuple(REVIT_VERSIONS)

    # -------------------------- жизненный цикл --------------------------
    def __post_init__(self) -> None:
        """Инициализирует границы поддерживаемого диапазона версий.

        :raises ValueError: Если список _supported_versions пуст.
        """
        if not self._supported_versions:
            raise ValueError(
                "revit_versions в settings.ini не может быть пустым "
                "или отсутствовать"
            )

        # Границы диапазона берём из канонического, уже отсортированного
        # списка _supported_versions.
        self._min_supported = self._supported_versions[0]
        self._max_supported = self._supported_versions[-1]

    # ----------------------- изменение состояния -----------------------
    def add_model(self, model: RevitModel, version: Optional[int]) -> None:
        """Добавляет модель в соответствующую корзину по версии.

        :param model:   Экземпляр модели Revit.
        :param version: Версия Revit модели или None, если её не удалось
                        определить.
        """
        # Не определили версию — отправляем в соответствующий лог.
        if version is None:
            self.logs.version_not_found.append(
                f"{model.rvt_path} — у модели не найдена версия Revit"
            )
            return

        # Версия выше поддерживаемого диапазона — фиксируем в лог.
        if version > self._max_supported:
            self.logs.version_too_new.append(
                f"{model.rvt_path} — версия Revit {version} выше "
                f"поддерживаемых ({self._min_supported}…{self._max_supported})"
            )
            return

        # Версия ниже минимума — используем минимум диапазона.
        if version < self._min_supported:
            version = self._min_supported

        # Помещаем модель в корзину своей версии.
        bucket = self.tasks.setdefault(version, [])
        bucket.append(model)

    def add_models(self, items: Iterable[ModelVersionPair]) -> None:
        """Массово добавляет модели по парам (model, version_or_none).

        :param items: Итератор пар (RevitModel, Optional[int]).
        """
        # Простой проход без накопления в памяти: сразу раскладываем
        # по корзинам через add_model().
        for model, version in items:
            self.add_model(model, version)

    # ------------------------ файловый вывод ---------------------------
    def write_task_files(self) -> None:
        """Создаёт файлы задач Task<версия>.txt по всем собранным версиям.

        Поведение:
            - версии обрабатываются по возрастанию;
            - внутри версии пути моделей сортируются по str(m.rvt_path);
            - по одной модели на строку.
        """
        # Обрабатываем версии по возрастанию для стабильного, предсказуемого
        # результата.
        for version in sorted(self.tasks.keys()):
            # Внутри версии сортируем пути моделей по строковому представлению.
            models = sorted(
                self.tasks[version],
                key=lambda m: str(m.rvt_path),
            )

            # Путь к файлу задачи определяется фасадом config.
            task_path = build_task_path(version)

            # (пока не используется)
            # если нужно будет переместить Task из admin_data,
            # то можно динамически создавать директорию
            # task_path.parent.mkdir(parents=True, exist_ok=True)

            # Одна строка = один путь к модели.
            task_path.write_text(
                "\n".join(str(m.rvt_path) for m in models),
                encoding="utf-8",
            )

    def write_tmp_csv(self, base_dir: Path, version: int) -> Path:
        """Создаёт временный CSV (<TMP_NAME>.csv) для указанной версии Revit.

        Формат строк (разделитель `;`):
            path;output_dir_mapping;mapping_json;family_mapping_file;
            output_dir_nomap;nomap_json

        :param base_dir: Папка, в которой создаётся <TMP_NAME>.csv.
        :param version:  Версия Revit, для которой формируется CSV.
        :return:         Полный путь к созданному файлу <TMP_NAME>.csv.
        """

        # (пока не используется)
        # если нужно будет переместить tmp из admin_data,
        # то можно динамически создавать директорию
        # base_dir.mkdir(parents=True, exist_ok=True)

        # Путь к CSV формируется через config.build_csv_path.
        tmp_path = build_csv_path(base_dir=base_dir)

        # Собираем строки только для указанной версии; порядок — по
        # строковому пути к модели.
        rows: List[List[str]] = []
        for model in sorted(
            self.tasks.get(version, []),
            key=lambda m: str(m.rvt_path),
        ):
            rows.append(
                [
                    str(model.rvt_path),
                    str(model.output_dir_mapping or ""),
                    str(model.mapping_json),
                    str(model.family_mapping_file),
                    str(model.output_dir_nomap or ""),
                    str(model.nomap_json or ""),
                ]
            )

        # Пишем CSV без заголовков — ревитовский скрипт ожидает
        # «чистые» данные.
        with tmp_path.open("w", encoding="utf-8-sig", newline="") as f:
            csv_writer = writer(f, delimiter=";")
            csv_writer.writerows(rows)

        return tmp_path
