# -*- coding: utf-8 -*-
"""Хелперы для поиска 3D-видов под экспорт.

Назначение:
    - Найти в документе 3D-вид по имени.
    - Предоставить обёртку для поиска 3D-вида по имени из settings.ini
      (параметр [Revit] export_view3d_name).

Контракты:
    - Рассматриваются только элементы класса Autodesk.Revit.DB.View3D.
    - Из выборки исключаются шаблонные виды (IsTemplate=True).
    - Имя вида сравнивается по точному совпадению, с учётом регистра.
    - При нескольких совпадениях возвращается первый найденный вид.
    - При отсутствии подходящих видов возвращается None.

Особенности:
    - Модуль может выполняться под IronPython 3.4 (pyRevit).
    - Допускается использование модуля typing для аннотаций типов, но без
      современного синтаксиса, требующего более новых версий Python
      (list[str], X | Y и т.п.) в исполняемом коде.
"""
from typing import Iterable, Optional, TypeVar

from config.settings import SETTINGS as STG

from revit._api import DB, FEC

__all__ = ["find_view3d_by_name", "find_export_view3d"]

T = TypeVar("T")

# Имя 3D-вида для экспорта из настроек ([Revit] export_view3d_name)
VIEW3D_EXPORT_NAME: str = STG.export_view3d_name


def find_export_view3d(doc: DB.Document) -> Optional[DB.View3D]:
    """Ищет 3D-вид для экспорта по имени из settings.ini.

    :param doc: Документ Revit.
    :return:    DB.View3D или None.
    """
    return find_view3d_by_name(doc, VIEW3D_EXPORT_NAME)


def find_view3d_by_name(doc: DB.Document, name: str) -> Optional[DB.View3D]:
    """Ищет 3D-вид по точному имени (регистр учитывается, не шаблон).

    Правила:
        - Рассматриваются только элементы класса View3D.
        - Исключаются шаблонные виды (IsTemplate=True).
        - Если найдено несколько видов, возвращается первый.
        - Сначала применяется фильтр по имени на стороне Revit API,
          затем fallback-перебор по всем 3D-видам.

    :param doc:  Документ Revit.
    :param name: Имя вида для точного сравнения.
    :return:     Autodesk.Revit.DB.View3D или None.
    """
    # --- Строим параметр-фильтр по имени вида (VIEW_NAME == name) ----------
    pvp = DB.ParameterValueProvider(
        DB.ElementId(DB.BuiltInParameter.VIEW_NAME)
    )
    # True = учитывать регистр
    rule = DB.FilterStringRule(pvp, DB.FilterStringEquals(), name, True)
    name_filter = DB.ElementParameterFilter(rule)

    # -- Сужаем набор на стороне Revit API (класс + фильтр + исключить типы) --
    col = (
        FEC(doc)
        .OfClass(DB.View3D)              # только 3D-виды # type: ignore
        .WherePasses(name_filter)        # фильтр по имени в ядре Revit
        .WhereElementIsNotElementType()  # исключить типовые элементы
    )

    # Берём первый не шаблонный вид; без промежуточных списков
    view = _first_or_none(x for x in col if not x.IsTemplate)
    if view is not None:
        return view

    # --- Fallback: на некоторых сборках строковые фильтры могут "молчать" ---
    col_all = FEC(doc).OfClass(  # type: ignore
        DB.View3D).WhereElementIsNotElementType()
    return _first_or_none(
        x for x in col_all if (not x.IsTemplate and x.Name == name)
    )


def _first_or_none(items: Iterable[T]) -> Optional[T]:
    """Возвращает первый элемент из итерируемого объекта или None.

    :param items: Итерируемая последовательность/генератор.
    :return:      Первый элемент или None, если элементов нет.
    """
    for x in items:
        return x
    return None
