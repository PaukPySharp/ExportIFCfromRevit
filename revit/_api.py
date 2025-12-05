# -*- coding: utf-8 -*-
"""Единая точка подключения Revit API и вспомогательных .NET-типов.

Назначение:
    - Экспортировать ключевые типы Revit API (DB, FEC) под удобными
      псевдонимами для остальных модулей проекта.
    - Подключать вспомогательные .NET-типы:
        * System.DateTime;
        * System.Collections.Generic.Dictionary;
        * System.Web.Script.Serialization.JavaScriptSerializer.
    - Ленивая загрузка IFC Exporter DLL и получение класса
      BIM.IFC.Export.UI.IFCExportConfiguration.

Контракты:
    - Путь к DLL экспорта IFC задаётся через настройки проекта:
      SETTINGS.main_dir + IFC_EXPORTER_DLL.
    - Функция get_ifc_export_config_class() загружает DLL только один раз
      за процесс и кэширует полученный класс в модуле.

Особенности:
    - Модуль может выполняться под IronPython 3.4 (pyRevit).
    - Допускается использование модуля typing для аннотаций типов, но без
      современного синтаксиса, требующего более новых версий Python
      (list[str], X | Y и т.п.) в исполняемом коде.
    - Подключение RevitAPI и System.Web.Extensions выполняется сразу
      при импорте модуля, чтобы остальные части кода могли использовать
      DB/FEC без повторного AddReference.
    - IFC Exporter DLL загружается лениво только при первом вызове
      get_ifc_export_config_class(), что уменьшает стоимость импорта
      revit._api в сценариях, где IFC-экспорт не используется.
"""
import clr
clr.AddReference("RevitAPI")
clr.AddReference("System.Web.Extensions")

from typing import Optional  # noqa: E402

from Autodesk.Revit import DB                                     # noqa: E402
from Autodesk.Revit.DB import FilteredElementCollector as FEC     # noqa: E402

from System import DateTime                                       # noqa: E402
from System.Collections.Generic import Dictionary                 # noqa: E402
from System.Web.Script.Serialization import JavaScriptSerializer  # noqa: E402
from config.settings import SETTINGS as STG                       # noqa: E402
from config.constants import IFC_EXPORTER_DLL                     # noqa: E402

__all__ = [
    "DB",
    "FEC",
    "DateTime",
    "Dictionary",
    "JavaScriptSerializer",
    "get_ifc_export_config_class",
]

# Кэш класса BIM.IFC.Export.UI.IFCExportConfiguration
_IFC_CFG_CLS: Optional[object] = None


def get_ifc_export_config_class() -> object:
    """Возвращает класс IFCExportConfiguration (с ленивой загрузкой DLL).

    Поведение:
        - При первом вызове:
            * строит путь к DLL как SETTINGS.main_dir / IFC_EXPORTER_DLL;
            * выполняет clr.AddReferenceToFileAndPath(dll_path);
            * импортирует BIM.IFC.Export.UI.IFCExportConfiguration
              и кэширует его в _IFC_CFG_CLS.
        - При последующих вызовах возвращает ранее закэшированный класс
          без повторной загрузки DLL.

    Исключения:
        - При отсутствии DLL или ошибке загрузки .NET-ассембли
          будет выброшено исключение уровня CLR/Python — оно
          не перехватывается здесь намеренно, чтобы проблема была
          видна вызывающему коду.

    :return: .NET-класс IFCExportConfiguration.
    """
    global _IFC_CFG_CLS

    if _IFC_CFG_CLS is None:
        # 1. Строим путь к DLL IFC Exporter.
        dll_path = STG.main_dir / IFC_EXPORTER_DLL
        # Проверяем, что DLL существует.
        if not dll_path.exists():
            raise FileNotFoundError(
                f"Файл {dll_path.name} не найден в папке: "
                f"{dll_path.parent}. Проверьте настройки проекта."
            )

        # 2. Загружаем .NET-ассембли из указанного файла.
        clr.AddReferenceToFileAndPath(str(dll_path))

        # 3. Импортируем класс конфигурации экспорта IFC и кэшируем его.
        from BIM.IFC.Export.UI import IFCExportConfiguration  # noqa: E402

        _IFC_CFG_CLS = IFCExportConfiguration

    return _IFC_CFG_CLS
