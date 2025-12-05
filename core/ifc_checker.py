# -*- coding: utf-8 -*-
"""Проверка актуальности IFC-файлов на диске.

Назначение:
    - Проверять, есть ли у модели «свежие» IFC-файлы:
        * с маппингом (mapped);
        * без маппинга (nomap), если такой сценарий включён.
    - Сравнивать время модификации IFC и RVT по единому стандарту
      «до минут» (как и во всём проекте).

Контракты:
    - IFC считается актуальным, если его mtime (округлённый до минут)
      не меньше, чем last_modified у RVT (также до минут).
    - is_ifc_up_to_date_mapping(model):
        * expected_ifc_path_mapping() вернул Path:
              → проверяем существование и «свежесть» файла;
        * expected_ifc_path_mapping() вернул None:
              → экспорт по mapped-направлению не настроен → False.
    - is_ifc_up_to_date_nomap(model):
        * expected_ifc_path_nomap() вернул None:
              → для модели nomap-выгрузка не требуется (либо глобально
                выключена, либо не настроена) → считаем условие выполненным,
                возвращаем True;
        * иначе проверяем существование и «свежесть» файла.

Особенности:
    - Для ускорения используется кэш по папкам:
        * {папка: {имя_файла: mtime(datetime, до минут)}}.
      Кэш лениво заполняется при первом обращении к папке.
    - Поиск файлов по маскам IFC_PATTERNS (по умолчанию только "*.ifc").
    - Ошибки доступа к файловой системе трактуются как «IFC не актуален»
      (возвращаем False, логируем на уровне debug).
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Iterable

from config import LOGGER_NAME

from core.models import RevitModel

from utils.fs import file_mtime_minute

# Модульный логгер
log = logging.getLogger(f"{LOGGER_NAME}.ifc_checker")

# Маски IFC-файлов (при необходимости можно расширить)
IFC_PATTERNS: tuple[str, ...] = ("*.ifc",)

# Метки для логов проверки IFC
LOG_LABEL_MAPPED = "Mapped-IFC"
LOG_LABEL_NOMAP = "Nomap-IFC"

# Кэш по одной папке: имя файла → время модификации (до минут)
FolderCache = Dict[str, datetime]
# Общий кэш: папка → FolderCache
IFCCache = Dict[Path, FolderCache]


class IFCChecker:
    """Проверка актуальности IFC-файлов для моделей Revit.

    Назначение:
        - По mtime файлов на диске определять, актуальны ли:
            * IFC с маппингом (mapped);
            * IFC без маппинга (nomap).

    Состояние:
        - _cache: IFCCache — кэш времени модификации IFC-файлов по папкам.

    Методы:
        - is_ifc_up_to_date_mapping(model: RevitModel) -> bool
        - is_ifc_up_to_date_nomap(model: RevitModel)   -> bool

    Особенности:
        - Класс не изменяет переданные экземпляры RevitModel.
          Решение об обнулении output_dir_* и формировании задач
          принимается в RevitModel.needs_export().
    """

    def __init__(self) -> None:
        """Инициализирует кэш по папкам для IFC-файлов.

        Структура кэша:
            - {папка: {имя_файла: mtime}},
              где mtime — datetime, нормализованный до минут.
        """
        self._cache: IFCCache = {}

    # ----------------------------- публичный API -----------------------------
    def is_ifc_up_to_date_mapping(self, model: RevitModel) -> bool:
        """Проверяет актуальность IFC с маппингом для модели.

        :param model: Экземпляр RevitModel с путями к папкам экспорта IFC.
        :return: True, если mapped-IFC существует и не старее RVT.
        """
        return self._check_ifc(
            path=model.expected_ifc_path_mapping(),
            model=model,
            log_label=LOG_LABEL_MAPPED,
            none_means_fresh=False,
        )

    def is_ifc_up_to_date_nomap(self, model: RevitModel) -> bool:
        """Проверяет актуальность IFC без маппинга для модели.

        :param model: Экземпляр RevitModel с путями к папкам экспорта IFC.
        :return: True, если nomap-IFC не требуется или существует
                 и не старее RVT.
        """
        return self._check_ifc(
            path=model.expected_ifc_path_nomap(),
            model=model,
            log_label=LOG_LABEL_NOMAP,
            none_means_fresh=True,
        )

    # ------------------------ внутренняя логика ------------------------
    def _check_ifc(
        self,
        path: Optional[Path],
        model: RevitModel,
        log_label: str,
        none_means_fresh: bool,
    ) -> bool:
        """Общая проверка для mapped/nomap-IFC.

        Поведение:
            - path is None:
                * при none_means_fresh=True условие считается выполненным;
                * при none_means_fresh=False считаем, что IFC не настроен.
            - path not None:
                * вызывается _is_fresh() и пишется debug-лог при устаревшем
                  или отсутствующем IFC.

        :param path: Ожидаемый путь к IFC-файлу или None.
        :param model: Экземпляр RevitModel (используется для логов и дат).
        :param log_label: Текстовая метка для логов
                          ("Mapped-IFC" / "Nomap-IFC").
        :param none_means_fresh: Если True, отсутствие пути трактуется как
                                 «условие выполнено» (для nomap-сценария).
        :return: True, если условие актуальности по данному направлению
                 считается выполненным.
        """
        if path is None:
            if none_means_fresh:
                # Для этой модели nomap-выгрузка не нужна → условие считаем
                # выполненным.
                log.debug(
                    "%s не требуется для модели: %s",
                    log_label,
                    model.rvt_path,
                )
                return True

            log.debug(
                "%s не настроен для модели (output_dir_* is None): %s",
                log_label,
                model.rvt_path,
            )
            return False

        # Путь задан — проверяем фактическую «свежесть» IFC относительно RVT.
        fresh = self._is_fresh(path, model.last_modified)
        if not fresh:
            # Для устаревшего/отсутствующего IFC фиксируем детальный debug-лог.
            log.debug(
                "%s устарел или отсутствует: %s (RVT mtime=%s)",
                log_label,
                path,
                model.last_modified,
            )
        return fresh

    def _is_fresh(self, ifc_path: Path, rvt_mtime: datetime) -> bool:
        """Проверяет, что IFC существует и его mtime (до минут) >= rvt_mtime.

        :param ifc_path: Ожидаемый путь к IFC-файлу.
        :param rvt_mtime: Время модификации RVT (уже нормализовано до минут).
        :return: True, если файл IFC существует и не старее RVT.
        """
        if not ifc_path.exists():
            log.debug("IFC-файл не найден: %s", ifc_path)
            return False

        ifc_mtime = self._cached_mtime(ifc_path)
        if ifc_mtime is None:
            log.debug(
                "Не удалось получить время модификации IFC-файла: %s",
                ifc_path,
            )
            return False

        if ifc_mtime < rvt_mtime:
            log.debug(
                "IFC-файл старее RVT: %s (IFC=%s < RVT=%s)",
                ifc_path,
                ifc_mtime,
                rvt_mtime,
            )
            return False

        # Сравниваем «минуты к минутам»
        return True

    def _cached_mtime(self, path: Path) -> Optional[datetime]:
        """Возвращает mtime файла из кэша папки (или обновляет кэш).

        :param path: Путь к файлу .ifc.
        :return: datetime (нормализован до минут) или None при
                 ошибке/отсутствии файла.
        """
        folder = path.parent
        name = path.name

        # Быстрый путь: кэш по папке уже есть.
        folder_cache = self._cache.get(folder)
        if folder_cache is not None:
            return folder_cache.get(name)

        # Кэша нет — собираем его для всей папки единым проходом.
        folder_cache = {}

        if not folder.exists():
            # Папка экспорта отсутствует: логируем и считаем, что IFC нет.
            log.debug("Папка IFC не существует: %s", folder)
            self._cache[folder] = folder_cache
            return None

        for f in self._iter_ifc_files(folder, patterns=IFC_PATTERNS):
            dt = file_mtime_minute(f)
            if dt is None:
                # Например, нет доступа к файлу или stat() упал.
                log.debug(
                    "Не удалось получить mtime IFC-файла, пропускаем "
                    "при кэшировании: %s",
                    f,
                )
                continue
            # Записываем данные отдельного файла
            folder_cache[f.name] = dt

        self._cache[folder] = folder_cache
        return folder_cache.get(name)

    @staticmethod
    def _iter_ifc_files(
        folder: Path,
        patterns: Iterable[str],
    ) -> Iterable[Path]:
        """Итерирует IFC-файлы по нескольким маскам с сортировкой по имени.

        Особенности:
            - Используются glob-паттерны из `patterns`;
            - Если папка не существует или пуста — вернётся пустой генератор;
            - Дубликаты (по разным маскам) убираются через set();
            - Порядок детерминирован: sorted() по имени файла.

        :param folder: Папка, где ищем файлы IFC.
        :param patterns: Маски (например, ("*.ifc",)).
        :return: Итератор по путям IFC-файлов.
        """
        # Гарантируем одинаковый порядок при каждом запуске
        files: list[Path] = []
        for pat in patterns:
            files.extend(folder.glob(pat))
        return (p for p in sorted(set(files)))

    # ------------------- будущие расширения (идеи) -------------------
    def __reset_cache(self) -> None:
        """
        Полностью сбрасывает кэш (например, перед новым крупным прогоном).
        """
        self._cache.clear()

    def __invalidate_folder(self, folder: Path) -> None:
        """Очищает кэш для указанной папки.

        :param folder: Папка, для которой нужно сбросить кэш.
        """
        self._cache.pop(folder, None)
