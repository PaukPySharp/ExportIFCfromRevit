# -*- coding: utf-8 -*-
import gc
from pathlib import Path

import clr
clr.AddReference("RevitAPI")

from Autodesk.Revit import DB

from const.constants import (
    FOLDER_LOGS,
    FOLDER_ADMIN_DATA,
    FOLDER_WITH_MAPPING,
    JSON_CONFIG_NOT_MAPPING,
    LAYERS,
    JSON_CONFIG,
    NAME_FOLDER_NOT_MAPPING
)

from func_revit.views import search_view3D_navisworks
from func_revit.import_data import get_data_about_path_and_mapping
from func_revit.configurations import (
    changing_config_file,
    create_configurations_export,
)

from func_main.logs import create_logs_file

from pyrevit import HOST_APP

# получаем данные из файла tmp со список моделей
data_about_path_and_mapping = get_data_about_path_and_mapping(
    FOLDER_ADMIN_DATA)

# создаем объект опций для открытия файла
options = DB.OpenOptions()
options.DetachFromCentralOption = DB.DetachFromCentralOption.DetachAndPreserveWorksets

list_not_valid_models = []  # список для моделей где нет вида Navisworks
list_errors_opening_models = []  # список для моделей с ошибками при открытии
for ind, _ in enumerate(__models__):
    # путь до модели и папки маппинга из списка
    # data_about_path_and_mapping по индексу
    path_model, mapping = data_about_path_and_mapping[ind]
    # пробуем открыть файл rvt
    try:
        # конвертирует строку с путем в класс ModelPath
        model_path = DB.ModelPathUtils.ConvertUserVisiblePathToModelPath(
            path_model)
        # получаем класс Document и путь до файла
        doc = HOST_APP.app.OpenDocumentFile(model_path, options)
    except Exception:
        # не получилось открыть файл, сохраняем запись
        # об этом в списке list_errors_opening_models
        list_errors_opening_models.append(
            f'{path_model} - модель не открылась в Revit')
        continue

    # находим 3D вид Navisworks
    view_navis = search_view3D_navisworks(doc)
    if view_navis is None:
        list_not_valid_models.append(
            f'{path_model} - в модели отсутствует вид Navisworks')
        continue

    # формирует пути до файлов маппирования
    family_mapping_file = (fr"{FOLDER_WITH_MAPPING}\{mapping}\{LAYERS}")
    json_config_mapping = fr"{FOLDER_WITH_MAPPING}\{mapping}\{JSON_CONFIG}"
    # изменяем данные в json файле конфигураций
    # для правильного чтения компьютером
    change_config_map = changing_config_file(json_config_mapping)
    change_config_not_map = changing_config_file(JSON_CONFIG_NOT_MAPPING)

    # создаем объекты с настроенными конфигурациями для экспорта ifc
    ifc_ex_options_map = create_configurations_export(
        family_mapping_file, change_config_map, view_navis.Id)
    ifc_ex_options_not_map = create_configurations_export(
        family_mapping_file, change_config_not_map, view_navis.Id)

    # открываем транзакцию для передачи данных в Revit
    with DB.Transaction(doc, 'ExportIFC') as t:
        t.Start()
        # переводим путь до rvt файла в класс Path
        path_model = Path(path_model)
        # формируем папку и имя ifc для выгрузки
        folder_model = str(path_model
                           .parent
                           .parent)
        name_ifc_file = path_model.stem
        # создаем папку куда попадут ifc без маппирования
        folder_empty_ifc = fr'{folder_model}\{NAME_FOLDER_NOT_MAPPING}'

        # экспорт ifc с маппированием
        doc.Export(
            folder_model,
            name_ifc_file,
            ifc_ex_options_map
        )

        # экспорт ifc без маппирования
        doc.Export(
            folder_empty_ifc,
            name_ifc_file,
            ifc_ex_options_not_map
        )

        t.RollBack()

    # === блок для сбора мусора ===
    doc.Close(False)  # закрываем документ
    gc.collect()  # сборщик мусора Python
    doc.Application.PurgeReleasedAPIObjects()  # сборщик мусора в Revit

# запись в лог список не открывшихся файлов Revit
if list_errors_opening_models:
    create_logs_file(
        FOLDER_LOGS,
        list_errors_opening_models,
        '1_errors_when_opening_models'
    )

# запись в лог не прошедших валидацию файлов
if list_not_valid_models:
    create_logs_file(
        FOLDER_LOGS,
        list_not_valid_models,
        '2_not_view_Navisworks_in_models'
    )
