# -*- coding: utf-8 -*-

# путь до папки с dll для экспорта ifc
IFC_EXPORTER_UI = (
    r"C:\Program Files\Autodesk\Revit 2022\AddIns\IFCExporterUI")

# список версий Revit с которыми может работать скрипт
LIST_VERSION_REVIT = sorted([
    2022,
    2023,
    2024,
])

# формат даты и времени
FORMAT_DATETIME = '%Y-%m-%d %H:%M'

# имена файлов с данными для маппирования
LAYERS = 'IFC_ExportLayers.txt'
JSON_CONFIG = 'IFC2x3_CV2.json'

# путь до файла с правилами выгрузки без маппирования
JSON_CONFIG_NOT_MAPPING = (
    r'%Путь до папки с настройками без маппирования%\IFC2x3_CV2_NoAtrributes.json'
)
NAME_FOLDER_NOT_MAPPING = '_IFC_NotMapping'

# пути до главной папки со скриптом и файлов маппирования
FOLDER_WITH_SCRIPT = r"C:\ExportIFCfromRevit"
FOLDER_WITH_MAPPING = r"%Путь до папки с шаблонами маппирования для различных проектов%\01_Шаблоны"

# ветвление для папки admin_data для запуска тестов
test = False
if test:
    FOLDER_ADMIN_DATA = fr"{FOLDER_WITH_SCRIPT}\admin_data"
else:
    FOLDER_ADMIN_DATA = r"%Путь на сервере с папкой admin_data%"

# путь до скрипта для передачи в Revit
SCRIPT_EXPORT_IFC = fr"{FOLDER_WITH_SCRIPT}\ExportIFC.py"

# пути до папок и файлов для работы процедуры
FOLDER_LOGS = fr'{FOLDER_ADMIN_DATA}\_logs'
MODELS_DICT_PATH = dict(
    (ver, fr"{FOLDER_ADMIN_DATA}\Task{ver}.txt")
    for ver in LIST_VERSION_REVIT
)
MANAGE_PATH = fr"{FOLDER_ADMIN_DATA}\manage.xlsx"
HISTORY_PATH = fr"{FOLDER_ADMIN_DATA}\history\history.xlsx"
