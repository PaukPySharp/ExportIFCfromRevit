# -*- coding: utf-8 -*-
"""Построение IFCExportOptions из JSON-конфига и файла маппинга.

Назначение:
    - Подготовить словарь настроек из JSON (правка даты/типов).
    - Построить DB.IFCExportOptions с применением IFCExportConfiguration.

Контракты:
    - JSON: UTF-8; поле ClassificationEditionDate содержит миллисекунды
      unix epoch в строке.
    - ActivePhaseId принудительно приводится к -1.
    - Сериализация конфигурации выполняется через JavaScriptSerializer;
      вложенные словари приводятся к Dictionary.

Особенности:
    - Модуль может выполняться под IronPython 3.4 (pyRevit).
    - Допускается использование модуля typing для аннотаций типов, но без
      современного синтаксиса, требующего более новых версий Python
      (list[str], X | Y и т.п.) в исполняемом коде.
"""
import re
import json

from ._api import (
    DB,
    DateTime,
    Dictionary,
    JavaScriptSerializer,  # type: ignore
    get_ifc_export_config_class,
)

# Фаза экспорта: -1 означает "активная фаза не задана явно".
ACTIVE_PHASE_ID = -1

__all__ = [
    "load_mapping_json",
    "build_ifc_export_options"
]


def load_mapping_json(mapping_json: str) -> Dictionary:
    """
    Считывает JSON и подготавливает словарь настроек для DeserializeFromJson.

    :param mapping_json: Путь к JSON-файлу настроек IFC.
    :return: Словарь настроек (.NET Dictionary, совместимый по структуре).
    """
    # 1. Читаем JSON-файл настроек экспорта
    with open(mapping_json, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 2. Дата классификатора хранится как строка с миллисекундами unix epoch.
    raw_date = cfg["ClassificationSettings"]["ClassificationEditionDate"]
    # Ищем первое целое число в строке
    m = re.search(r"-?\d+", raw_date)
    millis = int(m.group()) if m else 0

    # Превращаем миллисекунды в System.DateTime (1970-01-01 + millis)
    cfg["ClassificationSettings"]["ClassificationEditionDate"] = DateTime(
        1970, 1, 1
    ).AddMilliseconds(millis)  # type: ignore

    # 3. Фаза экспорта принудительно сбрасывается в -1
    cfg["ActivePhaseId"] = ACTIVE_PHASE_ID

    # 4. Приводим вложенные словари к .NET Dictionary
    cfg["ClassificationSettings"] = Dictionary[str, object](  # type: ignore
        cfg["ClassificationSettings"]
    )
    cfg["ProjectAddress"] = Dictionary[str, object](  # type: ignore
        cfg["ProjectAddress"]
    )
    cfg = Dictionary[str, object](cfg)  # type: ignore

    return cfg  # type: ignore


def build_ifc_export_options(
    family_mapping_file: str,
    change_config: Dictionary,
    navis_view_id: DB.ElementId,
) -> DB.IFCExportOptions:
    """Построить IFCExportOptions и применить настройки/вид.

    :param family_mapping_file: Путь к txt-файлу маппинга семейств/категорий.
    :param change_config:       Подготовленный словарь настроек
                                (результат load_mapping_json()).
    :param navis_view_id:       Идентификатор 3D-вида для экспорта.
    :return:                    Настроенный экземпляр DB.IFCExportOptions.
    """
    IFCExportConfiguration = get_ifc_export_config_class()

    # Создаём объект IFCExportOptions для применения настроек при выгрузке IFC
    ifc_opts: DB.IFCExportOptions = DB.IFCExportOptions()  # type: ignore
    # Применяем файл маппинга категорий/классов
    ifc_opts.FamilyMappingFile = family_mapping_file

    # Создаём объект IFCExportConfiguration для плагина по выгрузке IFC
    ifc_cfg = (IFCExportConfiguration.
               CreateDefaultConfiguration())  # type: ignore
    # Применяем изменённый JSON (change_config) через JavaScriptSerializer
    ifc_cfg.DeserializeFromJson(change_config, JavaScriptSerializer())

    # Применяем все изменения к IFCExportOptions и указываем 3D-вид экспорта
    ifc_cfg.UpdateOptions(ifc_opts, navis_view_id)

    return ifc_opts
