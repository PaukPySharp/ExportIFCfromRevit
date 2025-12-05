# -*- coding: utf-8 -*-
"""Чтение параметров экспорта из admin_data/<TMP_NAME>.csv.

Назначение:
    - Прочитать admin_data/<TMP_NAME>.csv и вернуть список ExportJob.

Контракты:
    - CSV: 6 колонок без заголовка; разделитель ';'; кодировка UTF-8-SIG.
    - Колонки соответствуют полям ExportJob (см. revit.jobs.ExportJob):
        0. rvt_path
        1. output_dir_mapping
        2. mapping_json
        3. family_mapping_file
        4. output_dir_nomap
        5. nomap_json
    - Путь к файлу <TMP_NAME>.csv формируется через
      config.files.build_csv_path(base_dir=...).
    - При отсутствии файла <TMP_NAME>.csv возвращается пустой список.

Особенности:
    - Модуль может выполняться под IronPython 3.4 (pyRevit).
    - Допускается использование модуля typing для аннотаций типов, но без
      современного синтаксиса, требующего более новых версий Python
      (list[str], X | Y и т.п.) в исполняемом коде.
    - Не зависит от pyRevit-API и может использоваться как из оркестратора,
      так и из скрипта под Revit.
"""
import csv
from pathlib import Path
from typing import List, Union

from config.files import build_csv_path

from revit.jobs import ExportJob

__all__ = ["iter_jobs"]

PathLike = Union[str, Path]


def iter_jobs(dir_admin_data: PathLike) -> List[ExportJob]:
    """Прочитать все задания из <TMP_NAME>.csv и вернуть список ExportJob.

    :param dir_admin_data: Путь к каталогу admin_data.
    :return: Список ExportJob в том порядке, как строки в <TMP_NAME>.csv.
    """
    base_dir = Path(dir_admin_data)

    # Путь к <TMP_NAME>.csv формируем через фасад config.files.
    tmp_csv = build_csv_path(base_dir=base_dir)

    jobs: List[ExportJob] = []
    if not tmp_csv.exists():
        return jobs

    # Читаем CSV в UTF-8-SIG, разделитель ';', без заголовка.
    with tmp_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        for row in reader:
            # Пропускаем полностью пустые строки.
            if not row:
                continue

            # Приводим строку к ровно 6 колонкам:
            #   - лишние значения обрезаются;
            #   - недостающие заполняются пустыми строками.
            row = (list(row) + [""] * 6)[:6]

            # Пустые строки в опциональных полях трактуем как отсутствие
            # значения (None), чтобы дальше не путать "" и "нет директории".
            jobs.append(
                ExportJob(
                    rvt_path=row[0],
                    output_dir_mapping=(row[1] or None),
                    mapping_json=row[2],
                    family_mapping_file=row[3],
                    output_dir_nomap=(row[4] or None),
                    nomap_json=(row[5] or None),
                )
            )

    return jobs
