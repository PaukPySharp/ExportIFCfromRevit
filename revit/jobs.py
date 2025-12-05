# -*- coding: utf-8 -*-
"""Структура данных ExportJob для одной RVT-модели.

Назначение:
    - Контейнер параметров экспорта для одной строки из
      ``admin_data/<TMP_NAME>.csv``.

Контракты:
    - CSV-файл без заголовка, разделитель ';'.
    - Колонки по индексам:
        0: rvt_path
           Путь к файлу *.rvt* (обязательно).
        1: output_dir_mapping
           Каталог выгрузки IFC с маппингом. Может быть пустым — тогда
           экспорт с маппингом для этой модели не выполняется.
        2: mapping_json
           Путь к JSON-файлу настроек экспорта (обязательно).
        3: family_mapping_file
           Путь к txt-файлу маппинга семейств/категорий (обязательно).
        4: output_dir_nomap
           Каталог выгрузки IFC без маппинга. Может быть пустым — тогда
           экспорт без маппинга для этой модели не выполняется.
        5: nomap_json
           Путь к JSON-файлу настроек экспорта без маппинга
           (может быть пустым).
    - Класс ExportJob нормализует все непустые пути в pathlib.Path.
    - Обязательные поля (колонки 0, 2, 3) не могут быть пустыми.

Особенности:
    - Модуль может выполняться под IronPython 3.4 (pyRevit).
    - Допускается использование модуля typing для аннотаций типов, но без
      современного синтаксиса, требующего более новых версий Python
      (list[str], X | Y и т.п.) в исполняемом коде.
"""
from pathlib import Path
from typing import Dict, Union, Optional

__all__ = ["ExportJob"]

PathLike = Union[Path, str]


class ExportJob(object):
    """Контейнер параметров экспорта для одной RVT-модели.

    Атрибуты:
        rvt_path:
            Путь к файлу *.rvt*.
        output_dir_mapping:
            Каталог выгрузки IFC с маппингом или None.
        mapping_json:
            JSON-файл настроек экспорта с маппингом.
        family_mapping_file:
            txt-файл маппинга семейств/категорий.
        output_dir_nomap:
            Каталог выгрузки IFC без маппинга или None.
        nomap_json:
            JSON-файл настроек экспорта без маппинга или None.

    Все непустые пути нормализуются в pathlib.Path, пустые опциональные
    значения интерпретируются как None.

    Подробный формат CSV и соответствие колонок описаны в модульном
    докстринге.
    """

    __slots__ = (
        "rvt_path",
        "output_dir_mapping",
        "mapping_json",
        "family_mapping_file",
        "output_dir_nomap",
        "nomap_json",
    )

    def __init__(
        self,
        rvt_path: PathLike,
        output_dir_mapping: Optional[PathLike],
        mapping_json: PathLike,
        family_mapping_file: PathLike,
        output_dir_nomap: Optional[PathLike] = None,
        nomap_json: Optional[PathLike] = None,
    ) -> None:
        """Инициализирует контейнер параметров экспорта.

        :param rvt_path: Путь к файлу *.rvt*.
        :param output_dir_mapping: Каталог выгрузки IFC с маппингом
            (None → экспорт с маппингом не выполняется).
        :param mapping_json: JSON-файл настроек экспорта (с маппингом).
        :param family_mapping_file: Файл маппинга семейств/категорий.
        :param output_dir_nomap: Каталог выгрузки IFC без маппинга
            (None → экспорт без маппинга не выполняется).
        :param nomap_json: JSON-файл настроек экспорта без маппинга
            (может быть None).
        """
        # 1. Обязательные поля
        self.rvt_path = _req_path(rvt_path, "rvt_path")
        self.mapping_json = _req_path(mapping_json, "mapping_json")
        self.family_mapping_file = _req_path(
            family_mapping_file,
            "family_mapping_file",
        )

        # 2. Опциональные поля
        self.output_dir_mapping = _opt_path(output_dir_mapping)
        self.output_dir_nomap = _opt_path(output_dir_nomap)
        self.nomap_json = _opt_path(nomap_json)

    def as_dict(self) -> Dict[str, object]:
        """Возвращает поля задания в виде словаря.

        Ключи совпадают с именами атрибутов из __slots__.
        """
        # Порядок ключей такой же, как в __slots__
        return {
            name: getattr(self, name)
            for name in self.__slots__
        }

    def __repr__(self) -> str:
        """Возвращает компактное строковое представление ExportJob.

        Используется только для отладки/логов, поэтому все пути
        приводятся к строкам (без WindowsPath(...) и т.п.), а
        опциональные поля отображаются как None, если не заданы.
        """
        data = self.as_dict()

        parts = []
        for name in self.__slots__:
            value = data[name]
            # None оставляем как есть, остальные значения приводим к str
            value = None if value is None else str(value)
            parts.append(f"{name}={value!r}")

        return "ExportJob(" + ", ".join(parts) + ")"


def _req_path(val: PathLike, field_name: str) -> Path:
    """Преобразует обязательное значение в Path.

    :param val: Значение (str или Path).
    :param field_name: Имя поля для сообщения об ошибке.
    :return: Path.
    :raises ValueError: Если значение пустое.
    """
    if not val:
        raise ValueError(f"ExportJob: '{field_name}' обязателен.")
    return val if isinstance(val, Path) else Path(val)


def _opt_path(val: Optional[PathLike]) -> Optional[Path]:
    """Преобразует опциональное значение в Path.

    :param val: Значение (str или Path) либо пустое.
    :return: Path или None.
    """
    if not val:
        return None
    return val if isinstance(val, Path) else Path(val)
