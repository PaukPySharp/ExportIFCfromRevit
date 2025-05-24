# -*- coding: utf-8 -*-
from const.constants import IFC_EXPORTER_UI

import json
import re
import sys
sys.path.append(IFC_EXPORTER_UI)


import clr
clr.AddReference("RevitAPI")
clr.AddReference('System.Web.Extensions')
clr.AddReference("Autodesk.IFC.Export.UI")

from Autodesk.Revit import DB
from BIM.IFC.Export.UI import IFCExportConfiguration

from System import DateTime
from System.Collections.Generic import Dictionary
from System.Web.Script.Serialization import JavaScriptSerializer


def changing_config_file(json_config: str) -> Dictionary[str, object]:
    with open(json_config, 'r', encoding='utf-8') as f:
        change_config = json.load(f)

    # получаю строчку с датой из загруженного json файла
    date_from_json = change_config['ClassificationSettings']['ClassificationEditionDate']
    # поиск числа внутри строчки с датой по регулярному выражению
    pars_date = re.search(r'-?\d+', date_from_json)
    # получаю найденное знание и перевожу в тип int
    millisec = int(pars_date.group())
    # прибавляю полученные миллисекунды к дате 1970-01-01 и получаю актуальную дату классификации
    change_config['ClassificationSettings']['ClassificationEditionDate'] = \
        DateTime(1970, 1, 1).AddMilliseconds(millisec)
    # меняем значение ActivePhaseId
    change_config['ActivePhaseId'] = -1
    # перевожу словари python в класс Dictionary платформы .net
    change_config['ClassificationSettings'] = \
        Dictionary[str, object](change_config['ClassificationSettings'])
    change_config['ProjectAddress'] = Dictionary[str, object](
        change_config['ProjectAddress'])
    change_config = Dictionary[str, object](change_config)

    return change_config


def create_configurations_export(family_mapping_file: str,
                                 change_config: Dictionary[str, object],
                                 navis_viewId: DB.ElementId) -> DB.IFCExportOptions:

    # создаем объект IFCExportOptions для применения к нему нужных настроек при выгрузке IFC
    ifc_ex_options = DB.IFCExportOptions()
    # применяем файл маппирования категорий/классов
    ifc_ex_options.FamilyMappingFile = family_mapping_file

    # создаем объект IFCExportConfiguration для плагина по выгрузке IFC
    ifc_ex_config = IFCExportConfiguration.CreateDefaultConfiguration()
    # применяем измененный json файл, который содержит нужные настройки к объекту IFCExportConfiguration
    ifc_ex_config.DeserializeFromJson(change_config, JavaScriptSerializer())

    # применяем все изменения к объекту IFCExportOptions и указываем нужный для экспорта 3D вид
    ifc_ex_config.UpdateOptions(ifc_ex_options, navis_viewId)

    return ifc_ex_options
