# -*- coding: utf-8 -*-
"""Хелперы для имён файлов (Windows).

Назначение:
    - Гарантированно добавлять нужное расширение к имени файла.
    - Отсеивать «грязные» .rvt-файлы (с несколькими расширениями).
    - Формировать базовое имя лог-файла моделей без 3D-вида по
      шаблону и настройкам Revit.

Контракты:
    - ensure_ext() не трогает пустые строки (возвращает как есть).
    - Сравнение расширений выполняется без учёта регистра.
    - is_pure_rvt() считает «чистым» только одинарное расширение ".rvt".
    - format_log_name_with_view() не изменяет template, если в нём нет
      подстроки "$$$"; имя вида по умолчанию берётся из настроек
      (раздел [Revit], параметр export_view3d_name).
"""
from pathlib import Path
from typing import Union

from config.settings import SETTINGS as STG
from config.constants import LOGFILE_MISSING_VIEW_TEMPLATE

PathLike = Union[str, Path]


def ensure_ext(name: str, default_ext: str) -> str:
    """Гарантирует расширение у имени файла.

    Правила:
        - Имя предварительно обрезается по краям (strip()).
        - Пустое имя возвращается как есть (без добавления расширения).
        - Если default_ext передано без точки, она будет добавлена.
        - Сравнение расширения выполняется без учёта регистра.

    :param name:        Имя файла (может быть с любым/без расширения).
    :param default_ext: Требуемое расширение (напр., ".txt" или "txt").
    :return:            Имя с гарантированным расширением.
    """
    n = name.strip()
    if not n:
        # пустую строку не переписываем
        return n

    ext = default_ext if default_ext.startswith(".") else f".{default_ext}"

    # Уже есть нужное расширение → возвращаем как есть.
    if n.lower().endswith(ext.lower()):
        return n

    # Дописываем расширение.
    return f"{n}{ext}"


def is_pure_rvt(p: PathLike) -> bool:
    """Проверяет, что у файла РОВНО одно расширение '.rvt'.

    Отсеивает:
        - 'Проект1.0001.rvt'
        - 'Проект1.IFC.RVT.rvt'
        - любые файлы с несколькими суффиксами.

    Пропускает:
        - 'Проект1.rvt'

    :param p: Путь к файлу (str или Path).
    :return:  True, если расширение одно и это '.rvt'; иначе False.
    """
    path = Path(p)
    return (len(path.suffixes) == 1) and (path.suffix.lower() == ".rvt")


def format_log_name_with_view(
    template: str = LOGFILE_MISSING_VIEW_TEMPLATE,
    view_name: str = STG.export_view3d_name,
) -> str:
    """Подставляет имя 3D-вида в шаблон базового имени лог-файла.

    Шаблон должен содержать подстроку "$$$", которая будет заменена
    на переданное имя вида. Если подстрока не найдена, шаблон
    возвращается как есть.

    :param template: Шаблон базового имени лог-файла
                     (например, "2_not_view_$$$_in_models").
    :param view_name: Имя 3D-вида для экспорта IFC.
                      По умолчанию берётся из настроек
                      (раздел [Revit], параметр export_view3d_name).
    :return:         Имя лог-файла с подставленным именем вида.
    """
    if "$$$" not in template:
        return template

    return template.replace("$$$", view_name)
